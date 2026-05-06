import sys
import ast
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import platform
import shutil
import subprocess

from lark import Token

from Viper_core.language import collect_program, get_type_name

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


HOST_OS_MAP = {
    "Darwin": "macos",
    "Linux": "linux",
    "Windows": "windows",
}

HOST_ARCH_MAP = {
    "x86_64": "x86_64",
    "AMD64": "x86_64",
    "arm64": "aarch64",
    "aarch64": "aarch64",
}


def detect_host_os():
    host_os = HOST_OS_MAP.get(platform.system())
    if host_os is None:
        raise ViperCompileError(f"VP: Error, Unsupported host OS '{platform.system()}'")
    return host_os


def detect_host_arch():
    return HOST_ARCH_MAP.get(platform.machine(), "x86_64")


def zig_target(target_os, target_arch):
    suffix = {
        "windows": "windows-gnu",
        "linux": "linux-gnu",
        "macos": "macos",
    }[target_os]
    return f"{target_arch}-{suffix}"


def executable_suffix(target_os):
    return ".exe" if target_os == "windows" else ""


def native_binary_path(c_path, target_os):
    return c_path.with_suffix(executable_suffix(target_os))


def compiler_candidates(host_os, target_os):
    target_arch = detect_host_arch()
    candidates = []

    if target_os == host_os:
        if host_os == "macos":
            candidates.extend([
                {"name": "cc", "kind": "posix"},
                {"name": "clang", "kind": "posix"},
                {"name": "gcc", "kind": "posix"},
            ])
        elif host_os == "linux":
            candidates.extend([
                {"name": "cc", "kind": "posix"},
                {"name": "clang", "kind": "posix"},
                {"name": "gcc", "kind": "posix"},
            ])
        elif host_os == "windows":
            candidates.extend([
                {"name": "cl", "kind": "msvc"},
                {"name": "clang-cl", "kind": "msvc"},
                {"name": "gcc", "kind": "posix"},
                {"name": "clang", "kind": "posix"},
            ])

    if target_os == "windows" and host_os != "windows":
        candidates.append({"name": "x86_64-w64-mingw32-gcc", "kind": "posix"})

    candidates.append({
        "name": "zig",
        "kind": "zig",
        "target": zig_target(target_os, target_arch),
    })

    return candidates


def find_compiler(host_os, target_os):
    for candidate in compiler_candidates(host_os, target_os):
        if shutil.which(candidate["name"]):
            return candidate
    return None


def compiler_command(candidate, c_path, binary_path):
    if candidate["kind"] == "posix":
        return [candidate["name"], str(c_path), "-o", str(binary_path)]

    if candidate["kind"] == "msvc":
        return [
            candidate["name"],
            str(c_path),
            "/nologo",
            f"/Fe:{binary_path}",
        ]

    if candidate["kind"] == "zig":
        return [
            candidate["name"],
            "cc",
            "-target",
            candidate["target"],
            str(c_path),
            "-o",
            str(binary_path),
        ]

    raise ViperCompileError(f"VP: Error, Unknown compiler kind '{candidate['kind']}'")


def build_binary(c_path, target_os="native", binary_path=None):
    host_os = detect_host_os()
    target_os = host_os if target_os == "native" else target_os

    if target_os not in {"macos", "linux", "windows"}:
        raise ViperCompileError(f"VP: Error, Unsupported target OS '{target_os}'")

    if binary_path is None:
        binary_path = native_binary_path(c_path, target_os)
    else:
        binary_path = Path(binary_path).resolve()

    candidate = find_compiler(host_os, target_os)
    if candidate is None:
        raise ViperCompileError(
            f"VP: Error, No suitable C compiler found for host '{host_os}' and target '{target_os}'"
        )

    command = compiler_command(candidate, c_path, binary_path)

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        details = error.stderr.strip() or error.stdout.strip() or "unknown compiler error"
        raise ViperCompileError(
            f"VP: Error, C compilation failed with '{candidate['name']}'\n    {details}"
        ) from error

    return binary_path, candidate["name"]


def require_supported_type(type_name, context):
    if type_name not in SUPPORTED_RUNTIME_TYPES:
        raise ViperCompileError(f"VP: Error, {context} uses unsupported compile target type '{type_name}'")


class CCompiler:
    def __init__(self, program):
        self.program = program
        self.functions = program["functions"]

    def compile(self):
        for function in self.functions.values():
            require_supported_type(function["ret_type"], "Function")

        lines = [
            "#include <stdbool.h>",
            "#include <stdio.h>",
            "#include <stdlib.h>",
            "#include <string.h>",
            "",
            "static int vp_argc = 0;",
            "static char **vp_argv = NULL;",
            "",
            "static char *vp_collect(void) {",
            "    char buffer[4096];",
            "    if (fgets(buffer, sizeof(buffer), stdin) == NULL) {",
            "        buffer[0] = '\\0';",
            "    }",
            "    buffer[strcspn(buffer, \"\\r\\n\")] = '\\0';",
            "    size_t length = strlen(buffer) + 1;",
            "    char *copy = (char *)malloc(length);",
            "    if (copy == NULL) {",
            "        fputs(\"VP: Error, Failed to collect input\\n\", stderr);",
            "        exit(1);",
            "    }",
            "    memcpy(copy, buffer, length);",
            "    return copy;",
            "}",
            "",
            "static char *vp_collect_prompt(const char *prompt) {",
            "    if (prompt != NULL) {",
            "        fputs(prompt, stdout);",
            "        fflush(stdout);",
            "    }",
            "    return vp_collect();",
            "}",
            "",
            "static void vp_print_int(long long value) { printf(\"%lld\\n\", value); }",
            "static void vp_print_double(double value) { printf(\"%g\\n\", value); }",
            "static void vp_print_bool(bool value) { puts(value ? \"true\" : \"false\"); }",
            "static void vp_print_str(const char *value) { puts(value == NULL ? \"\" : value); }",
            "static void vp_print_char(char value) { printf(\"%c\\n\", value); }",
            "static void vp_print_none(void *value) { (void)value; puts(\"none\"); }",
            "",
            "static char *vp_int_to_str(long long value) {",
            "    int length = snprintf(NULL, 0, \"%lld\", value);",
            "    char *text = (char *)malloc((size_t)length + 1);",
            "    if (text == NULL) {",
            "        fputs(\"VP: Error, Failed to convert int to string\\n\", stderr);",
            "        exit(1);",
            "    }",
            "    snprintf(text, (size_t)length + 1, \"%lld\", value);",
            "    return text;",
            "}",
            "",
            "static char *vp_double_to_str(double value) {",
            "    int length = snprintf(NULL, 0, \"%g\", value);",
            "    char *text = (char *)malloc((size_t)length + 1);",
            "    if (text == NULL) {",
            "        fputs(\"VP: Error, Failed to convert number to string\\n\", stderr);",
            "        exit(1);",
            "    }",
            "    snprintf(text, (size_t)length + 1, \"%g\", value);",
            "    return text;",
            "}",
            "",
            "static const char *vp_bool_to_str(bool value) { return value ? \"true\" : \"false\"; }",
            "static const char *vp_none_to_str(void *value) { (void)value; return \"none\"; }",
            "",
            "static char *vp_char_to_str(char value) {",
            "    char *text = (char *)malloc(2);",
            "    if (text == NULL) {",
            "        fputs(\"VP: Error, Failed to convert char to string\\n\", stderr);",
            "        exit(1);",
            "    }",
            "    text[0] = value;",
            "    text[1] = '\\0';",
            "    return text;",
            "}",
            "",
            "static char *vp_concat_str(const char *left, const char *right) {",
            "    if (left == NULL) { left = \"\"; }",
            "    if (right == NULL) { right = \"\"; }",
            "    size_t left_length = strlen(left);",
            "    size_t right_length = strlen(right);",
            "    char *combined = (char *)malloc(left_length + right_length + 1);",
            "    if (combined == NULL) {",
            "        fputs(\"VP: Error, Failed to concatenate strings\\n\", stderr);",
            "        exit(1);",
            "    }",
            "    memcpy(combined, left, left_length);",
            "    memcpy(combined + left_length, right, right_length + 1);",
            "    return combined;",
            "}",
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
            declared_type = get_type_name(node.children[1], ViperCompileError)
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

        if node.data == "collect_stmt":
            if node.children:
                prompt_code, prompt_type = self.emit_expr(node.children[0], scope)
                return [f"{indent}(void)vp_collect_prompt({self.to_string_expr(prompt_code, prompt_type)});"]
            return [f"{indent}(void)vp_collect();"]

        if node.data == "call_stmt":
            name = str(node.children[0])
            if name == "collect":
                return [f"{indent}(void)vp_collect();"]
            if name not in self.functions:
                raise ViperCompileError(f"VP: Error, Undefined function '{name}'")
            return [f"{indent}{self.c_function_name(name)}();"]

        if node.data == "if_stmt":
            return self.emit_if_stmt(node, scope, indent_level)

        if node.data == "try_stmt":
            return self.emit_try_stmt(node, scope, indent_level)

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

    def emit_try_stmt(self, node, scope, indent_level):
        indent = "    " * indent_level
        lines = [f"{indent}{{"]
        for statement in node.children[0].children:
            try:
                lines.extend(self.emit_statement(statement, scope, indent_level + 1))
            except ViperCompileError:
                continue
        lines.append(f"{indent}}}")
        return lines

    def emit_expr(self, node, scope):
        if isinstance(node, Token):
            raise ViperCompileError(f"VP: Error, Unexpected token '{node}' in expression")

        data = node.data

        if data == "string":
            return self.c_string_literal(ast.literal_eval(str(node.children[0]))), "str"

        if data == "fstring":
            return self.emit_interpolated_string(str(node.children[0]), scope)

        if data == "char":
            return str(node.children[0]), "char"

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

        if data == "collect":
            if node.children:
                prompt_code, prompt_type = self.emit_expr(node.children[0], scope)
                return f"vp_collect_prompt({self.to_string_expr(prompt_code, prompt_type)})", "str"
            return "vp_collect()", "str"

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

        if data == "add":
            left_code, left_type = self.emit_expr(node.children[0], scope)
            right_code, right_type = self.emit_expr(node.children[1], scope)
            if self.is_stringish(left_type) or self.is_stringish(right_type):
                return f"vp_concat_str({self.to_string_expr(left_code, left_type)}, {self.to_string_expr(right_code, right_type)})", "str"
            self.ensure_numeric(left_type, data)
            self.ensure_numeric(right_type, data)
            result_type = self.numeric_result_type(left_type, right_type)
            return f"({left_code} + {right_code})", result_type

        if data in {"sub", "mul"}:
            left_code, left_type = self.emit_expr(node.children[0], scope)
            right_code, right_type = self.emit_expr(node.children[1], scope)
            self.ensure_numeric(left_type, data)
            self.ensure_numeric(right_type, data)
            result_type = self.numeric_result_type(left_type, right_type)
            symbol = { "sub": "-", "mul": "*" }[data]
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
            if self.is_stringish(left_type) and self.is_stringish(right_type) and data in {"eq", "ne"}:
                compare_code = f"(strcmp({self.to_string_expr(left_code, left_type)}, {self.to_string_expr(right_code, right_type)}) == 0)"
                if data == "ne":
                    compare_code = f"!{compare_code}"
                return compare_code, "bool"
            return f"({left_code} {COMPARISON_SYMBOLS[data]} {right_code})", "bool"

        raise ViperCompileError(f"VP: Error, Unknown expression '{data}'")

    def ensure_assignable(self, declared_type, expr_type, name):
        if declared_type == "int":
            ok = expr_type == "int"
        elif declared_type in {"float", "double"}:
            ok = expr_type in {"int", "float", "double"}
        elif declared_type == "str":
            ok = expr_type in {"str", "char"}
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

        if self.is_stringish(left_type) and self.is_stringish(right_type):
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
        if declared_type == "str" and expr_type == "char":
            return self.to_string_expr(expr_code, expr_type)
        if declared_type in {"float", "double"} and expr_type == "int":
            return f"((double)({expr_code}))"
        return expr_code

    def is_stringish(self, type_name):
        return type_name in {"str", "char"}

    def to_string_expr(self, expr_code, expr_type):
        if expr_type == "str":
            return expr_code
        if expr_type == "char":
            return f"vp_char_to_str({expr_code})"
        if expr_type == "int":
            return f"vp_int_to_str({expr_code})"
        if expr_type in {"float", "double"}:
            return f"vp_double_to_str({expr_code})"
        if expr_type == "bool":
            return f"vp_bool_to_str({expr_code})"
        if expr_type == "none":
            return f"vp_none_to_str({expr_code})"
        raise ViperCompileError(f"VP: Error, Cannot use type '{expr_type}' as a string")

    def emit_interpolated_string(self, token_text, scope):
        template = ast.literal_eval(token_text[1:])
        parts = []
        cursor = 0

        for match in re.finditer(r"\[([A-Za-z_][A-Za-z0-9_]*|\$[A-Za-z_][A-Za-z0-9_]*)\]", template):
            if match.start() > cursor:
                parts.append((self.c_string_literal(template[cursor:match.start()]), "str"))
            parts.append(self.emit_interpolated_value(match.group(1), scope))
            cursor = match.end()

        if cursor < len(template):
            parts.append((self.c_string_literal(template[cursor:]), "str"))

        if not parts:
            return self.c_string_literal(template), "str"

        expr_code, expr_type = parts[0]
        expr_code = self.to_string_expr(expr_code, expr_type)
        for part_code, part_type in parts[1:]:
            expr_code = f"vp_concat_str({expr_code}, {self.to_string_expr(part_code, part_type)})"

        return expr_code, "str"

    def emit_interpolated_value(self, name, scope):
        if name == "$argc":
            return "vp_argc", "int"
        if name == "$args":
            return "vp_argv", "str[]"

        variable_name = name[1:] if name.startswith("$") else name
        if variable_name not in scope.variables:
            raise ViperCompileError(f"VP: Error, Unknown variable '{variable_name}'")
        return variable_name, scope.variables[variable_name]

    def c_string_literal(self, text):
        return json.dumps(text)

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

    program = collect_program(input_path, error_cls=ViperCompileError)
    compiler = CCompiler(program)
    c_source = compiler.compile()

    if output_path is None:
        output_path = input_path.with_suffix(".c")
    else:
        output_path = Path(output_path).resolve()

    output_path.write_text(c_source, encoding="utf-8")
    return output_path


def parse_cli_args(argv):
    args = list(argv)
    target_os = "native"

    if len(args) >= 2 and args[0] == "--target":
        target_os = args[1].lower()
        args = args[2:]

    if not args:
        raise ViperCompileError(
            "Usage: python Viper_compiler/main.py [--target native|macos|linux|windows] <file.vp> [output.c] [output_binary]"
        )

    input_path = args[0]
    output_c = args[1] if len(args) >= 2 else None
    output_binary = args[2] if len(args) >= 3 else None

    if len(args) > 3:
        raise ViperCompileError(
            "Usage: python Viper_compiler/main.py [--target native|macos|linux|windows] <file.vp> [output.c] [output_binary]"
        )

    return input_path, output_c, output_binary, target_os


def main():
    try:
        input_path, output_c, output_binary, target_os = parse_cli_args(sys.argv[1:])
        written_path = compile_file(input_path, output_c)
        binary_path, compiler_name = build_binary(written_path, target_os, output_binary)
        print(f"Wrote {written_path}")
        print(f"Built {binary_path} with {compiler_name}")
        return 0
    except ViperCompileError as error:
        print(error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
