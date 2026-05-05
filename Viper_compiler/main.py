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

print_stmt: "print" "(" expr ")" ";"
var_stmt: "$" NAME ":" type "=" expr ";"
assign_stmt: "$" NAME "=" expr ";"
return_stmt: "return" expr ";"
call_stmt: NAME "(" ")" ";"
if_stmt: "if" "(" expr ")" block else_if_clause* else_clause?
else_if_clause: "else" "if" "(" expr ")" block
else_clause: "else" block
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

C_TYPE_MAP = {
    "int": "long long",
    "void": "void",
    "float": "double",
    "double": "double",
    "str": "const char *",
    "char": "char",
    "bool": "bool",
    "none": "void *",
    "char[]": "char *",
    "int[]": "void *",
    "float[]": "void *",
    "double[]": "void *",
    "str[]": "char **",
}

SUPPORTED_RUNTIME_TYPES = {"int", "float", "double", "str", "char", "bool", "none", "void", "str[]"}
COMPARISON_SYMBOLS = {
    "eq": "==",
    "ne": "!=",
    "lt": "<",
    "le": "<=",
    "gt": ">",
    "ge": ">=",
}


class ViperCompileError(RuntimeError):
    pass


class Scope:
    def __init__(self):
        self.variables = {}


parser = Lark(VIPER_GRAMMAR, parser="lalr")


def parse_source(source_code, filename):
    try:
        return parser.parse(source_code)
    except Exception as error:
        raise ViperCompileError(f"{filename}: VP: Parse error\n    {error}") from error


def extract_string(token):
    text = str(token)
    return text[1:-1]


def resolve_import_path(raw_path, importer_path):
    if raw_path.startswith("/"):
        return Path(raw_path).resolve()

    return (importer_path.parent / raw_path).resolve()


def get_type_name(type_node):
    type_name = TYPE_NAME_MAP.get(type_node.data)
    if type_name is None:
        raise ViperCompileError(f"VP: Error, Unknown type '{type_node.data}'")
    return type_name


def require_supported_type(type_name, context):
    if type_name not in SUPPORTED_RUNTIME_TYPES:
        raise ViperCompileError(f"VP: Error, {context} uses unsupported compile target type '{type_name}'")


def collect_program(root_path):
    root_path = root_path.resolve()
    root_source = root_path.read_text(encoding="utf-8")
    root_tree = parse_source(root_source, str(root_path))

    functions = {}
    loaded_files = set()
    active_files = set()

    def visit(tree, current_path):
        current_path = current_path.resolve()

        if current_path in active_files:
            raise ViperCompileError(f"VP: Error, Circular import detected for '{current_path}'")

        if current_path in loaded_files:
            return

        active_files.add(current_path)

        for item in tree.children:
            child = item.children[0]

            if child.data == "import_stmt":
                import_target = extract_string(child.children[0])
                import_path = resolve_import_path(import_target, current_path)

                if not import_path.exists():
                    raise ViperCompileError(f"VP: Error, Imported file not found: {import_target}")

                import_tree = parse_source(import_path.read_text(encoding="utf-8"), str(import_path))
                visit(import_tree, import_path)

            elif child.data == "func_def":
                ret_type = get_type_name(child.children[0])
                require_supported_type(ret_type, "Function")

                name = str(child.children[1])
                if name in functions:
                    raise ViperCompileError(
                        f"VP: Error, Function '{name}' already defined in '{functions[name]['source']}'"
                    )

                functions[name] = {
                    "name": name,
                    "ret_type": ret_type,
                    "body": child.children[2],
                    "source": str(current_path),
                }

        active_files.remove(current_path)
        loaded_files.add(current_path)

    visit(root_tree, root_path)

    top_level_statements = []
    for item in root_tree.children:
        child = item.children[0]
        if child.data == "statement":
            top_level_statements.append(child.children[0])

    return {
        "root_path": root_path,
        "tree": root_tree,
        "functions": functions,
        "top_level_statements": top_level_statements,
    }


class CCompiler:
    def __init__(self, program):
        self.program = program
        self.functions = program["functions"]

    def compile(self):
        lines = [
            "#include <stdbool.h>",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "",
            "static int vp_argc = 0;",
            "static char **vp_argv = NULL;",
            "",
            "static void vp_print_int(long long value) { printf(\"%lld\\n\", value); }",
            "static void vp_print_double(double value) { printf(\"%g\\n\", value); }",
            "static void vp_print_bool(bool value) { puts(value ? \"true\" : \"false\"); }",
            "static void vp_print_str(const char *value) { puts(value == NULL ? \"\" : value); }",
            "static void vp_print_char(char value) { printf(\"%c\\n\", value); }",
            "static void vp_print_none(void *value) { (void)value; puts(\"none\"); }",
            "",
        ]

        prototypes = []
        for name, function in self.functions.items():
            prototypes.append(f"static {self.c_type(function['ret_type'])} {self.c_function_name(name)}(void);")

        if prototypes:
            lines.extend(prototypes)
            lines.append("")

        for function in self.functions.values():
            lines.extend(self.emit_function(function))
            lines.append("")

        lines.extend(self.emit_c_main())
        return "\n".join(lines).rstrip() + "\n"

    def emit_function(self, function):
        lines = [f"static {self.c_type(function['ret_type'])} {self.c_function_name(function['name'])}(void) {{"]
        scope = Scope()
        lines.extend(self.emit_block(function["body"], scope, 1))

        if function["ret_type"] == "void":
            if not self.block_guarantees_return(function["body"]):
                lines.append("    return;")
        elif not self.block_guarantees_return(function["body"]):
            zero_value = self.zero_value(function["ret_type"])
            lines.append(
                f"    fprintf(stderr, \"VP: Error, Function '{function['name']}' declared '{function['ret_type']}' but did not return a value\\n\");"
            )
            lines.append(f"    return {zero_value};")

        lines.append("}")
        return lines

    def emit_c_main(self):
        lines = ["int main(int argc, char **argv) {", "    vp_argc = argc > 1 ? argc - 1 : 0;", "    vp_argv = argc > 1 ? argv + 1 : argv;"]

        if "main" in self.functions:
            ret_type = self.functions["main"]["ret_type"]
            c_name = self.c_function_name("main")

            if ret_type == "int":
                lines.append(f"    return (int){c_name}();")
            elif ret_type == "void":
                lines.append(f"    {c_name}();")
                lines.append("    return 0;")
            else:
                lines.append(f"    (void){c_name}();")
                lines.append("    return 0;")
        else:
            scope = Scope()
            lines.extend(self.emit_statements(self.program["top_level_statements"], scope, 1))
            lines.append("    return 0;")

        lines.append("}")
        return lines

    def emit_block(self, block_node, scope, indent_level):
        return self.emit_statements(block_node.children, scope, indent_level)

    def emit_statements(self, statements, scope, indent_level):
        lines = []
        for statement in statements:
            lines.extend(self.emit_statement(statement, scope, indent_level))
        return lines

    def emit_statement(self, node, scope, indent_level):
        if node.data == "statement":
            return self.emit_statement(node.children[0], scope, indent_level)

        indent = "    " * indent_level

        if node.data == "print_stmt":
            expr_code, expr_type = self.emit_expr(node.children[0], scope)
            return [f"{indent}{self.print_function(expr_type)}({expr_code});"]

        if node.data == "var_stmt":
            name = str(node.children[0])
            declared_type = get_type_name(node.children[1])
            require_supported_type(declared_type, "Variable")

            expr_code, expr_type = self.emit_expr(node.children[2], scope)
            self.ensure_assignable(declared_type, expr_type, name)
            scope.variables[name] = declared_type
            return [f"{indent}{self.c_type(declared_type)} {name} = {self.cast_expr(expr_code, expr_type, declared_type)};"]

        if node.data == "assign_stmt":
            name = str(node.children[0])
            if name not in scope.variables:
                raise ViperCompileError(f"VP: Error, Variable '{name}' not declared")

            declared_type = scope.variables[name]
            expr_code, expr_type = self.emit_expr(node.children[1], scope)
            self.ensure_assignable(declared_type, expr_type, name)
            return [f"{indent}{name} = {self.cast_expr(expr_code, expr_type, declared_type)};"]

        if node.data == "return_stmt":
            expr_code, _ = self.emit_expr(node.children[0], scope)
            return [f"{indent}return {expr_code};"]

        if node.data == "call_stmt":
            name = str(node.children[0])
            if name not in self.functions:
                raise ViperCompileError(f"VP: Error, Undefined function '{name}'")
            return [f"{indent}{self.c_function_name(name)}();"]

        if node.data == "if_stmt":
            return self.emit_if_stmt(node, scope, indent_level)

        raise ViperCompileError(f"VP: Error, Unknown statement '{node.data}'")

    def emit_if_stmt(self, node, scope, indent_level):
        lines = []
        indent = "    " * indent_level
        condition_code, condition_type = self.emit_expr(node.children[0], scope)
        if condition_type != "bool":
            raise ViperCompileError("VP: Error, If conditions must evaluate to bool")

        lines.append(f"{indent}if ({condition_code}) {{")
        lines.extend(self.emit_block(node.children[1], scope, indent_level + 1))
        lines.append(f"{indent}}}")

        for clause in node.children[2:]:
            if clause.data == "else_if_clause":
                else_if_condition, else_if_type = self.emit_expr(clause.children[0], scope)
                if else_if_type != "bool":
                    raise ViperCompileError("VP: Error, If conditions must evaluate to bool")
                lines.append(f"{indent}else if ({else_if_condition}) {{")
                lines.extend(self.emit_block(clause.children[1], scope, indent_level + 1))
                lines.append(f"{indent}}}")
            elif clause.data == "else_clause":
                lines.append(f"{indent}else {{")
                lines.extend(self.emit_block(clause.children[0], scope, indent_level + 1))
                lines.append(f"{indent}}}")

        return lines

    def emit_expr(self, node, scope):
        if isinstance(node, Token):
            raise ViperCompileError(f"VP: Error, Unexpected token '{node}' in expression")

        data = node.data

        if data == "string":
            return str(node.children[0]), "str"

        if data == "number":
            text = str(node.children[0])
            return (text, "double") if "." in text else (text, "int")

        if data == "true":
            return "true", "bool"

        if data == "false":
            return "false", "bool"

        if data == "none_literal":
            return "NULL", "none"

        if data == "argc":
            return "vp_argc", "int"

        if data == "args":
            return "vp_argv", "str[]"

        if data == "variable":
            name = str(node.children[0])
            if name not in scope.variables:
                raise ViperCompileError(f"VP: Error, Unknown variable '{name}'")
            return name, scope.variables[name]

        if data == "call_expr":
            name = str(node.children[0])
            if name not in self.functions:
                raise ViperCompileError(f"VP: Error, Undefined function '{name}'")
            ret_type = self.functions[name]["ret_type"]
            if ret_type == "void":
                raise ViperCompileError(f"VP: Error, Function '{name}' returns void and cannot be used in an expression")
            return f"{self.c_function_name(name)}()", ret_type

        if data in {"add", "sub", "mul"}:
            left_code, left_type = self.emit_expr(node.children[0], scope)
            right_code, right_type = self.emit_expr(node.children[1], scope)
            self.ensure_numeric(left_type, data)
            self.ensure_numeric(right_type, data)
            result_type = self.numeric_result_type(left_type, right_type)
            symbol = { "add": "+", "sub": "-", "mul": "*" }[data]
            return f"({left_code} {symbol} {right_code})", result_type

        if data == "div":
            left_code, left_type = self.emit_expr(node.children[0], scope)
            right_code, right_type = self.emit_expr(node.children[1], scope)
            self.ensure_numeric(left_type, data)
            self.ensure_numeric(right_type, data)
            return f"((double)({left_code}) / (double)({right_code}))", "double"

        if data == "neg":
            value_code, value_type = self.emit_expr(node.children[0], scope)
            self.ensure_numeric(value_type, data)
            return f"(-({value_code}))", value_type

        if data == "and_op":
            left_code, left_type = self.emit_expr(node.children[0], scope)
            right_code, right_type = self.emit_expr(node.children[1], scope)
            if left_type != "bool" or right_type != "bool":
                raise ViperCompileError("VP: Error, Operator 'and' requires bool operands")
            return f"({left_code} && {right_code})", "bool"

        if data in COMPARISON_SYMBOLS:
            left_code, left_type = self.emit_expr(node.children[0], scope)
            right_code, right_type = self.emit_expr(node.children[1], scope)
            self.ensure_comparable(data, left_type, right_type)
            return f"({left_code} {COMPARISON_SYMBOLS[data]} {right_code})", "bool"

        raise ViperCompileError(f"VP: Error, Unknown expression '{data}'")

    def ensure_assignable(self, declared_type, expr_type, name):
        if declared_type == "int":
            ok = expr_type == "int"
        elif declared_type in {"float", "double"}:
            ok = expr_type in {"int", "float", "double"}
        elif declared_type == "str":
            ok = expr_type == "str"
        elif declared_type == "char":
            ok = expr_type == "char"
        elif declared_type == "bool":
            ok = expr_type == "bool"
        elif declared_type == "none":
            ok = expr_type == "none"
        elif declared_type == "void":
            ok = expr_type == "none"
        elif declared_type == "str[]":
            ok = expr_type == "str[]"
        else:
            ok = False

        if not ok:
            raise ViperCompileError(
                f"VP: Error, Cannot assign {expr_type} to '{declared_type}' variable '{name}'"
            )

    def ensure_numeric(self, type_name, operator_name):
        if type_name not in {"int", "float", "double"}:
            raise ViperCompileError(f"VP: Error, Operator '{self.operator_symbol(operator_name)}' requires numeric operands")

    def ensure_comparable(self, operator_name, left_type, right_type):
        if operator_name in {"lt", "le", "gt", "ge"}:
            self.ensure_numeric(left_type, operator_name)
            self.ensure_numeric(right_type, operator_name)
            return

        if left_type in {"int", "float", "double"} and right_type in {"int", "float", "double"}:
            return

        if left_type == right_type:
            return

        raise ViperCompileError(
            f"VP: Error, Operator '{self.operator_symbol(operator_name)}' requires comparable operands"
        )

    def numeric_result_type(self, left_type, right_type):
        if left_type in {"float", "double"} or right_type in {"float", "double"}:
            return "double"
        return "int"

    def c_type(self, type_name):
        c_type = C_TYPE_MAP.get(type_name)
        if c_type is None:
            raise ViperCompileError(f"VP: Error, Unsupported compile target type '{type_name}'")
        return c_type

    def c_function_name(self, name):
        if name == "main":
            return "vp_user_main"
        return name

    def cast_expr(self, expr_code, expr_type, declared_type):
        if declared_type in {"float", "double"} and expr_type == "int":
            return f"((double)({expr_code}))"
        return expr_code

    def print_function(self, type_name):
        mapping = {
            "int": "vp_print_int",
            "float": "vp_print_double",
            "double": "vp_print_double",
            "str": "vp_print_str",
            "char": "vp_print_char",
            "bool": "vp_print_bool",
            "none": "vp_print_none",
        }
        if type_name not in mapping:
            raise ViperCompileError(f"VP: Error, Cannot print unsupported type '{type_name}'")
        return mapping[type_name]

    def zero_value(self, type_name):
        return {
            "int": "0",
            "float": "0.0",
            "double": "0.0",
            "str": "NULL",
            "char": "'\\0'",
            "bool": "false",
            "none": "NULL",
        }[type_name]

    def operator_symbol(self, operator_name):
        return {
            "add": "+",
            "sub": "-",
            "mul": "*",
            "div": "/",
            **COMPARISON_SYMBOLS,
        }[operator_name]

    def block_guarantees_return(self, block_node):
        for statement in block_node.children:
            if self.statement_guarantees_return(statement):
                return True
        return False

    def statement_guarantees_return(self, node):
        if node.data == "statement":
            return self.statement_guarantees_return(node.children[0])

        if node.data == "return_stmt":
            return True

        if node.data != "if_stmt":
            return False

        has_else = False
        branch_returns = [self.block_guarantees_return(node.children[1])]

        for clause in node.children[2:]:
            if clause.data == "else_if_clause":
                branch_returns.append(self.block_guarantees_return(clause.children[1]))
            elif clause.data == "else_clause":
                has_else = True
                branch_returns.append(self.block_guarantees_return(clause.children[0]))

        return has_else and all(branch_returns)


def compile_file(input_path, output_path=None):
    input_path = Path(input_path).resolve()

    if not input_path.exists():
        raise ViperCompileError(f"VP: Error, File not found: {input_path}")

    if input_path.suffix != ".vp":
        raise ViperCompileError(f"VP: Error, Expected a .vp file, received: {input_path.suffix}")

    program = collect_program(input_path)
    compiler = CCompiler(program)
    c_source = compiler.compile()

    if output_path is None:
        output_path = input_path.with_suffix(".c")
    else:
        output_path = Path(output_path).resolve()

    output_path.write_text(c_source, encoding="utf-8")
    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python Viper_compiler/main.py <file.vp> [output.c]")
        return 1

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        written_path = compile_file(input_path, output_path)
        print(f"Wrote {written_path}")
        return 0
    except ViperCompileError as error:
        print(error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
