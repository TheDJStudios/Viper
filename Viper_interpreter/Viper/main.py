import sys
from pathlib import Path
from lark import Lark, Token


VIPER_GRAMMAR = r"""
start: item*

item: import_stmt
    | func_def
    | statement

import_stmt: "import" STRING ";"
func_def: type NAME "(" ")" block

statement: print_stmt
         | var_stmt
         | assign_stmt
         | return_stmt
         | call_stmt
         | if_stmt
         | try_stmt

print_stmt: "print" "(" expr ")" ";"
var_stmt: "$" NAME ":" type "=" expr ";"
assign_stmt: "$" NAME "=" expr ";"
return_stmt: "return" expr ";"
call_stmt: NAME "(" ")" ";"
if_stmt: "if" "(" expr ")" block else_if_clause* else_clause?
else_if_clause: "else" "if" "(" expr ")" block
else_clause: "else" block
try_stmt: "try" block
block: "{" statement* "}"

type: "int"      -> int_type
    | "void"     -> void_type
    | "float"    -> float_type
    | "double"   -> double_type
    | "str"      -> str_type
    | "string"   -> string_type
    | "char"     -> char_type
    | "bool"     -> bool_type
    | "none"     -> none_type
    | "char[]"   -> char_arr_type
    | "int[]"    -> int_arr_type
    | "float[]"  -> float_arr_type
    | "double[]" -> double_arr_type
    | "str[]"    -> str_arr_type
    | "string[]" -> string_arr_type

?expr: expr "and" comparison -> and_op
     | comparison

?comparison: arithmetic "==" arithmetic -> eq
           | arithmetic "!=" arithmetic -> ne
           | arithmetic "<=" arithmetic -> le
           | arithmetic ">=" arithmetic -> ge
           | arithmetic "<" arithmetic  -> lt
           | arithmetic ">" arithmetic  -> gt
           | arithmetic

?arithmetic: arithmetic "+" term -> add
           | arithmetic "-" term -> sub
           | term

?term: term "*" unary -> mul
     | term "/" unary -> div
     | unary

?unary: "-" unary -> neg
      | atom

?atom: STRING     -> string
     | NUMBER     -> number
     | "true"     -> true
     | "false"    -> false
     | "none"     -> none_literal
     | "collect" "(" ")" -> collect
     | NAME "(" ")" -> call_expr
     | "$argc"    -> argc
     | "$args"    -> args
     | "$" NAME   -> variable
     | NAME       -> variable
     | "(" expr ")"

%import common.CNAME -> NAME
%import common.ESCAPED_STRING -> STRING
%import common.NUMBER
%import common.WS
%ignore WS

COMMENT: /%[^\n]*/
%ignore COMMENT
"""


class ReturnSignal(Exception):
    def __init__(self, value):
        super().__init__("return")
        self.value = value


class ViperRuntimeError(RuntimeError):
    pass


TYPE_NAME_MAP = {
    "int_type": "int",
    "void_type": "void",
    "float_type": "float",
    "double_type": "double",
    "str_type": "str",
    "string_type": "str",
    "char_type": "char",
    "bool_type": "bool",
    "none_type": "none",
    "char_arr_type": "char[]",
    "int_arr_type": "int[]",
    "float_arr_type": "float[]",
    "double_arr_type": "double[]",
    "str_arr_type": "str[]",
    "string_arr_type": "str[]",
}


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
            text = str(node.children[0])
            return text[1:-1]

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
            return self.collect_input()

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

    def collect_input(self):
        try:
            return input()
        except EOFError:
            return ""

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


parser = Lark(VIPER_GRAMMAR, parser="lalr")


def parse_source(source_code, filename):
    try:
        return parser.parse(source_code)
    except Exception as error:
        raise ViperRuntimeError(f"{filename}: VP: Parse error\n    {error}") from error


def resolve_import_path(raw_path, importer_path):
    if raw_path.startswith("/"):
        return Path(raw_path).resolve()

    if importer_path == Path("<stdin>"):
        base_dir = Path.cwd()
    else:
        base_dir = importer_path.parent

    return (base_dir / raw_path).resolve()


def extract_string(token):
    text = str(token)
    return text[1:-1]


def hoist_functions(tree, filename, functions, loaded_files, active_files):
    resolved_filename = filename.resolve()

    if resolved_filename in active_files:
        raise ViperRuntimeError(f"VP: Error, Circular import detected for '{resolved_filename}'")

    if resolved_filename in loaded_files:
        return

    active_files.add(resolved_filename)

    for item in tree.children:
        child = item.children[0]

        if child.data == "import_stmt":
            import_target = extract_string(child.children[0])
            import_path = resolve_import_path(import_target, resolved_filename)

            if not import_path.exists():
                raise ViperRuntimeError(
                    f"VP: Error, Imported file not found: {import_target}"
                )

            import_source = import_path.read_text(encoding="utf-8")
            import_tree = parse_source(import_source, str(import_path))
            hoist_functions(import_tree, import_path, functions, loaded_files, active_files)

        elif child.data == "func_def":
            func_type = child.children[0]
            func_name = str(child.children[1])
            func_body = child.children[2]
            ret_type = TYPE_NAME_MAP.get(func_type.data)

            if ret_type is None:
                raise ViperRuntimeError(f"VP: Error, Unknown type '{func_type.data}'")

            if func_name in functions:
                existing_file = functions[func_name]["source"]
                raise ViperRuntimeError(
                    f"VP: Error, Function '{func_name}' already defined in '{existing_file}'"
                )

            functions[func_name] = {
                "ret_type": ret_type,
                "body": func_body,
                "source": str(resolved_filename),
            }

    active_files.remove(resolved_filename)
    loaded_files.add(resolved_filename)


def runsource(source_code, filename="<stdin>", vp_args=None):
    source_path = Path(filename).resolve() if filename != "<stdin>" else Path("<stdin>")
    vp_args = sys.argv[2:] if vp_args is None else vp_args

    try:
        tree = parse_source(source_code, filename)
        functions = {}
        hoist_functions(tree, source_path, functions, set(), set())
        interpreter = ViperInterpreter(functions, vp_args)

        if "main" in functions:
            result = interpreter.call_function("main")

            if isinstance(result, int) and not isinstance(result, bool):
                return result

            return 0

        interpreter.run_items(tree.children)
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
