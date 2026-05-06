import sys
import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lark import Token

from Viper_core.language import TYPE_NAME_MAP, collect_program


class ReturnSignal(Exception):
    def __init__(self, value):
        super().__init__("return")
        self.value = value


class ViperRuntimeError(RuntimeError):
    pass


class ViperInterpreter:
    def __init__(self, functions, vp_args):
        self.functions = functions
        self.vp_args = list(vp_args)
        self.variables = {}

    def run_items(self, items):
        for item in items:
            self.execute_item(item)

    def execute_item(self, node):
        if node.data != "item":
            raise ViperRuntimeError(f"VP: Error, Unknown item '{node.data}'")

        child = node.children[0]

        if child.data == "statement":
            self.execute_statement(child.children[0])
            return

        if child.data in {"func_def", "import_stmt"}:
            return

        raise ViperRuntimeError(f"VP: Error, Unknown item '{child.data}'")

    def execute_statement(self, node):
        if node.data == "statement":
            self.execute_statement(node.children[0])
            return

        if node.data == "print_stmt":
            value = self.evaluate_expr(node.children[0])
            print(self.format_value(value))
            return

        if node.data == "var_stmt":
            name = str(node.children[0])
            declared_type = self.get_type_name(node.children[1])
            value = self.evaluate_expr(node.children[2])

            if name in self.variables:
                raise ViperRuntimeError(f"VP: Error, Variable '{name}' already declared")

            if not self.value_matches_type(value, declared_type):
                actual_type = self.get_value_type_name(value)
                raise ViperRuntimeError(
                    f"VP: Error, Cannot assign {actual_type} to '{declared_type}' variable '{name}'"
                )

            self.variables[name] = {"type": declared_type, "value": value}
            return

        if node.data == "assign_stmt":
            name = str(node.children[0])
            value = self.evaluate_expr(node.children[1])

            if name not in self.variables:
                raise ViperRuntimeError(f"VP: Error, Variable '{name}' not declared")

            declared_type = self.variables[name]["type"]
            if not self.value_matches_type(value, declared_type):
                actual_type = self.get_value_type_name(value)
                raise ViperRuntimeError(
                    f"VP: Error, Cannot assign {actual_type} to '{declared_type}' variable '{name}'"
                )

            self.variables[name]["value"] = value
            return

        if node.data == "return_stmt":
            value = self.evaluate_expr(node.children[0])
            raise ReturnSignal(value)

        if node.data == "collect_stmt":
            prompt = self.evaluate_expr(node.children[0]) if node.children else None
            self.collect_input(prompt)
            return

        if node.data == "call_stmt":
            name = str(node.children[0])
            if name == "collect":
                self.collect_input()
                return
            self.call_function(name)
            return

        if node.data == "if_stmt":
            self.execute_if_stmt(node)
            return

        if node.data == "try_stmt":
            self.execute_try_stmt(node)
            return

        raise ViperRuntimeError(f"VP: Error, Unknown statement '{node.data}'")

    def execute_if_stmt(self, node):
        condition = self.evaluate_expr(node.children[0])
        self.require_bool_condition(condition)

        if condition:
            self.execute_block(node.children[1])
            return

        for clause in node.children[2:]:
            if clause.data == "else_if_clause":
                else_if_condition = self.evaluate_expr(clause.children[0])
                self.require_bool_condition(else_if_condition)

                if else_if_condition:
                    self.execute_block(clause.children[1])
                    return

            elif clause.data == "else_clause":
                self.execute_block(clause.children[0])
                return

    def execute_try_stmt(self, node):
        try:
            self.execute_block(node.children[0])
        except ViperRuntimeError:
            return

    def execute_block(self, block_node):
        for statement in block_node.children:
            self.execute_statement(statement)

    def evaluate_expr(self, node):
        if isinstance(node, Token):
            raise ViperRuntimeError(f"VP: Error, Unexpected token '{node}' in expression")

        data = node.data

        if data == "string":
            return ast.literal_eval(str(node.children[0]))

        if data == "fstring":
            return self.evaluate_interpolated_string(str(node.children[0]))

        if data == "char":
            return ast.literal_eval(str(node.children[0]))

        if data == "number":
            text = str(node.children[0])
            return float(text) if "." in text else int(text)

        if data == "true":
            return True

        if data == "false":
            return False

        if data == "none_literal":
            return None

        if data == "argc":
            return len(self.vp_args)

        if data == "args":
            return list(self.vp_args)

        if data == "collect":
            prompt = self.evaluate_expr(node.children[0]) if node.children else None
            return self.collect_input(prompt)

        if data == "variable":
            name = str(node.children[0])
            if name not in self.variables:
                raise ViperRuntimeError(f"VP: Error, Unknown variable '{name}'")
            return self.variables[name]["value"]

        if data == "call_expr":
            return self.call_function(str(node.children[0]))

        if data == "add":
            left = self.evaluate_expr(node.children[0])
            right = self.evaluate_expr(node.children[1])
            if isinstance(left, str) or isinstance(right, str):
                return str(self.format_value(left)) + str(self.format_value(right))
            self.require_numeric_operands("+", left, right)
            return left + right

        if data == "sub":
            left = self.evaluate_expr(node.children[0])
            right = self.evaluate_expr(node.children[1])
            self.require_numeric_operands("-", left, right)
            return left - right

        if data == "mul":
            left = self.evaluate_expr(node.children[0])
            right = self.evaluate_expr(node.children[1])
            self.require_numeric_operands("*", left, right)
            return left * right

        if data == "div":
            left = self.evaluate_expr(node.children[0])
            right = self.evaluate_expr(node.children[1])
            self.require_numeric_operands("/", left, right)
            if right == 0:
                raise ViperRuntimeError("VP: Error, Division by zero")
            return left / right

        if data == "neg":
            value = self.evaluate_expr(node.children[0])
            if not self.is_number(value):
                raise ViperRuntimeError("VP: Error, Unary '-' requires a numeric operand")
            return -value

        if data == "and_op":
            left = self.evaluate_expr(node.children[0])
            self.require_bool_operand("and", left)
            if not left:
                return False
            right = self.evaluate_expr(node.children[1])
            self.require_bool_operand("and", right)
            return left and right

        if data in {"eq", "ne", "lt", "le", "gt", "ge"}:
            left = self.evaluate_expr(node.children[0])
            right = self.evaluate_expr(node.children[1])
            return self.evaluate_comparison(data, left, right)

        raise ViperRuntimeError(f"VP: Error, Unknown expression '{data}'")

    def collect_input(self, prompt=None):
        if prompt is not None:
            print(self.format_value(prompt), end="", flush=True)
        try:
            return input()
        except EOFError:
            return ""

    def evaluate_interpolated_string(self, token_text):
        template = ast.literal_eval(token_text[1:])

        def replace(match):
            name = match.group(1)
            value = self.lookup_interpolated_value(name)
            return str(self.format_value(value))

        return re.sub(r"\[([A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z_][A-Za-z0-9_]*)\]", replace, template)

    def lookup_interpolated_value(self, name):
        if name == "$argc":
            return len(self.vp_args)
        if name == "$args":
            return list(self.vp_args)

        variable_name = name[1:] if name.startswith("$") else name
        if variable_name not in self.variables:
            raise ViperRuntimeError(f"VP: Error, Unknown variable '{variable_name}'")
        return self.variables[variable_name]["value"]

    def call_function(self, name):
        if name not in self.functions:
            raise ViperRuntimeError(f"VP: Error, Undefined function '{name}'")

        function = self.functions[name]
        saved_variables = self.variables.copy()
        result = None

        try:
            self.execute_block(function["body"])
        except ReturnSignal as signal:
            result = signal.value
        finally:
            self.variables = saved_variables

        if function["ret_type"] == "void":
            if result is not None:
                actual_type = self.get_value_type_name(result)
                raise ViperRuntimeError(
                    f"VP: Error, Function '{name}' declared 'void' but returned {actual_type}"
                )
            return None

        if result is None:
            raise ViperRuntimeError(
                f"VP: Error, Function '{name}' declared '{function['ret_type']}' but did not return a value"
            )

        if not self.value_matches_type(result, function["ret_type"]):
            actual_type = self.get_value_type_name(result)
            raise ViperRuntimeError(
                f"VP: Error, Function '{name}' returned {actual_type} but is declared '{function['ret_type']}'"
            )

        return result

    def evaluate_comparison(self, operator_name, left, right):
        if operator_name in {"lt", "le", "gt", "ge"}:
            self.require_numeric_operands(self.operator_symbol(operator_name), left, right)
        elif not self.comparable_for_equality(left, right):
            raise ViperRuntimeError(
                f"VP: Error, Operator '{self.operator_symbol(operator_name)}' requires comparable operands"
            )

        if operator_name == "eq":
            return left == right
        if operator_name == "ne":
            return left != right
        if operator_name == "lt":
            return left < right
        if operator_name == "le":
            return left <= right
        if operator_name == "gt":
            return left > right
        if operator_name == "ge":
            return left >= right

        raise ViperRuntimeError(f"VP: Error, Unknown comparison operator '{operator_name}'")

    def operator_symbol(self, operator_name):
        return {
            "eq": "==",
            "ne": "!=",
            "lt": "<",
            "le": "<=",
            "gt": ">",
            "ge": ">=",
        }[operator_name]

    def require_bool_condition(self, value):
        if not isinstance(value, bool):
            raise ViperRuntimeError("VP: Error, If conditions must evaluate to bool")

    def require_bool_operand(self, operator_name, value):
        if not isinstance(value, bool):
            raise ViperRuntimeError(
                f"VP: Error, Operator '{operator_name}' requires bool operands"
            )

    def require_numeric_operands(self, operator_name, left, right):
        if not self.is_number(left) or not self.is_number(right):
            raise ViperRuntimeError(
                f"VP: Error, Operator '{operator_name}' requires numeric operands"
            )

    def comparable_for_equality(self, left, right):
        if self.is_number(left) and self.is_number(right):
            return True
        return self.get_value_type_name(left) == self.get_value_type_name(right)

    def is_number(self, value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def get_type_name(self, node):
        if node.data not in TYPE_NAME_MAP:
            raise ViperRuntimeError(f"VP: Error, Unknown type '{node.data}'")

        return TYPE_NAME_MAP[node.data]

    def get_value_type_name(self, value):
        if value is None:
            return "none"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, list):
            return "list"
        return type(value).__name__

    def value_matches_type(self, value, expected_type):
        if expected_type == "int":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type in {"float", "double"}:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "str":
            return isinstance(value, str)
        if expected_type == "char":
            return isinstance(value, str) and len(value) == 1
        if expected_type == "bool":
            return isinstance(value, bool)
        if expected_type == "none":
            return value is None
        if expected_type == "void":
            return value is None
        if expected_type.endswith("[]"):
            return isinstance(value, list)
        return False

    def format_value(self, value):
        if value is None:
            return "none"
        if value is True:
            return "true"
        if value is False:
            return "false"
        return value

def runsource(source_code, filename="<stdin>", vp_args=None):
    source_path = Path(filename).resolve() if filename != "<stdin>" else Path("<stdin>")
    vp_args = sys.argv[2:] if vp_args is None else vp_args

    try:
        program = collect_program(source_path, source_code=source_code, error_cls=ViperRuntimeError)
        interpreter = ViperInterpreter(program["functions"], vp_args)

        if "main" in program["functions"]:
            result = interpreter.call_function("main")

            if isinstance(result, int) and not isinstance(result, bool):
                return result

            return 0

        interpreter.run_items(program["tree"].children)
        return 0

    except ReturnSignal:
        print(f"{filename}: VP: Error, 'return' is only valid inside a function")
        return 1

    except ViperRuntimeError as error:
        print(error)
        return 1


def runviperfile(filepath):
    path = Path(filepath)

    if not path.exists():
        print(f"VP: Error occurred, File not found: {filepath}")
        return 1

    if path.suffix != ".vp":
        print(f"VP: Error occurred, Expected a .vp file, received: {path.suffix}")
        return 1

    sourcecode = path.read_text(encoding="utf-8")
    return runsource(sourcecode, str(path))


def main():
    if len(sys.argv) < 2:
        print("Usage: python /Viper_interpreter/Viper/main.py <file.vp>")
        return 1

    return runviperfile(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
