#!/bin/python3
import sys
from pathlib import Path
from lark import Lark, Transformer, v_args
from lark.exceptions import VisitError


VALID_TYPES = {
    "int", "void", "float", "double", "string", "char",
    "char[]", "int[]", "float[]", "double[]", "string[]",
}

VIPER_GRAMMAR = r"""
start: item*

item: func_def
    | statement

func_def: type CNAME "()" "{" statement* "}"

statement: print_stmt
         | var_stmt
         | assign_stmt
         | return_stmt
         | call_stmt

print_stmt:  "print" "(" expr ")" ";"
var_stmt:    "$" CNAME ":" type "=" expr ";"
assign_stmt: "$" CNAME "=" expr ";"
return_stmt: "return" expr ";"
call_stmt:   CNAME "()" ";"

type: "int"      -> int_type
    | "void"     -> void_type
    | "float"    -> float_type
    | "double"   -> double_type
    | "string"   -> string_type
    | "char"     -> char_type
    | "char[]"   -> char_arr_type
    | "int[]"    -> int_arr_type
    | "float[]"  -> float_arr_type
    | "double[]" -> double_arr_type
    | "string[]" -> string_arr_type

expr: STRING         -> string
    | NUMBER         -> number
    | "true"         -> true
    | "false"        -> false
    | "$" CNAME      -> variable
    | CNAME "()"     -> call_expr
    | "$argc"        -> argc
    | "$args"        -> args

%import common.CNAME
%import common.ESCAPED_STRING -> STRING
%import common.NUMBER
%import common.WS
%ignore WS

COMMENT: /%[^\n]*/
%ignore COMMENT
"""

_TYPE_MAP = {
    "int_type":       "int",
    "void_type":      "void",
    "float_type":     "float",
    "double_type":    "double",
    "string_type":    "string",
    "char_type":      "char",
    "char_arr_type":  "char[]",
    "int_arr_type":   "int[]",
    "float_arr_type": "float[]",
    "double_arr_type":"double[]",
    "string_arr_type":"string[]",
}


class ReturnSignal(BaseException):
    """unwinds the call stack on return, BaseException so lark won't wrap it"""
    def __init__(self, value):
        self.value = value


def unwrap_visit_error(e):
    """peel nested VisitError wrappers down to the real cause"""
    while isinstance(e, VisitError):
        e = e.orig_exc
    return e


@v_args(inline=True)
class ViperTransformer(Transformer):
    def __init__(self, vp_args: list, functions: dict):
        super().__init__()
        self.variables = {}
        self.vp_args = vp_args
        self.functions = functions

    # types
    def int_type(self):         return "int"
    def void_type(self):        return "void"
    def float_type(self):       return "float"
    def double_type(self):      return "double"
    def string_type(self):      return "string"
    def char_type(self):        return "char"
    def char_arr_type(self):    return "char[]"
    def int_arr_type(self):     return "int[]"
    def float_arr_type(self):   return "float[]"
    def double_arr_type(self):  return "double[]"
    def string_arr_type(self):  return "string[]"

    # literals
    def string(self, token):    return str(token)[1:-1]
    def number(self, token):
        s = str(token)
        return float(s) if "." in s else int(s)
    def true(self):             return True
    def false(self):            return False

    # builtins
    def argc(self):             return len(self.vp_args)
    def args(self):             return self.vp_args

    def variable(self, name):
        name = str(name)
        if name not in self.variables:
            raise RuntimeError(f"VP: Error, Unknown variable '${name}'")
        return self.variables[name]["value"]

    def call_expr(self, name):
        return self._call(str(name))

    def _call(self, name: str):
        if name not in self.functions:
            raise RuntimeError(f"VP: Error, Undefined function '{name}'")

        fn = self.functions[name]
        ret_type = fn["ret_type"]
        body = fn["body"]

        saved = self.variables.copy()
        result = None
        try:
            for stmt in body:
                try:
                    self.transform(stmt)
                except ReturnSignal:
                    raise
                except VisitError as e:
                    orig = unwrap_visit_error(e)
                    raise orig
        except ReturnSignal as r:
            result = r.value
        finally:
            self.variables = saved

        if ret_type != "void" and result is None:
            raise RuntimeError(
                f"VP: Error, Function '{name}' declared '{ret_type}' but did not return a value"
            )
        return result

    # statements
    def print_stmt(self, value):
        print(value)

    def call_stmt(self, name):
        self._call(str(name))

    def return_stmt(self, value):
        raise ReturnSignal(value)

    def var_stmt(self, name, var_type, value):
        name = str(name)
        if name in self.variables:
            raise RuntimeError(f"VP: Error, Variable '${name}' already declared")
        if not self._type_matches(value, var_type):
            raise RuntimeError(
                f"VP: Error, Cannot assign {type(value).__name__} to '{var_type}' variable '${name}'"
            )
        self.variables[name] = {"type": var_type, "value": value}

    def assign_stmt(self, name, value):
        name = str(name)
        if name not in self.variables:
            raise RuntimeError(f"VP: Error, Variable '${name}' not declared")
        expected = self.variables[name]["type"]
        if not self._type_matches(value, expected):
            raise RuntimeError(
                f"VP: Error, Cannot assign {type(value).__name__} to '{expected}' variable '${name}'"
            )
        self.variables[name]["value"] = value

    def _type_matches(self, value, expected_type: str) -> bool:
        if expected_type == "int":               return isinstance(value, int) and not isinstance(value, bool)
        if expected_type in ("float", "double"): return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type in ("string", "char[]"): return isinstance(value, str)
        if expected_type == "char":              return isinstance(value, str) and len(value) == 1
        if expected_type == "void":              return value is None
        if expected_type.endswith("[]"):         return isinstance(value, list)
        if expected_type == "bool":              return isinstance(value, bool)
        return False

    def statement(self, stmt=None):  return stmt
    def item(self, item=None):       return item
    def start(self, *items):         return items


parser = Lark(VIPER_GRAMMAR, parser="lalr")


def hoist_functions(tree) -> dict:
    functions = {}
    for item in tree.children:
        node = item.children[0] if item.children else None
        if node is None or not hasattr(node, "data") or node.data != "func_def":
            continue
        ret_type = _TYPE_MAP.get(node.children[0].data, "unknown")
        name = str(node.children[1])
        body = list(node.children[2:])
        functions[name] = {"ret_type": ret_type, "body": body}
    return functions


def runsource(source_code: str, filename: str = "<stdin>"):
    vp_args = sys.argv[2:]

    try:
        tree = parser.parse(source_code)
    except Exception as e:
        print(f"{filename}: VP: Parse error")
        print(f"    {e}")
        return

    functions = hoist_functions(tree)
    interpreter = ViperTransformer(vp_args, functions)

    def run_block(body):
        saved = interpreter.variables.copy()
        try:
            for stmt in body:
                try:
                    interpreter.transform(stmt)
                except ReturnSignal:
                    raise
                except VisitError as e:
                    orig = unwrap_visit_error(e)
                    if isinstance(orig, ReturnSignal):
                        raise orig
                    raise orig
        except ReturnSignal as r:
            return r.value
        finally:
            interpreter.variables = saved
        return None

    try:
        if "main" in functions:
            exit_code = run_block(functions["main"]["body"])
            fn_ret = functions["main"]["ret_type"]

            if fn_ret != "void" and exit_code is None:
                print(f"{filename}: VP: Error, 'main' declared '{fn_ret}' but did not return a value")
                sys.exit(1)

            sys.exit(exit_code if isinstance(exit_code, int) else 0)
        else:
            # fallback: run top-level non-function statements
            for item in tree.children:
                node = item.children[0] if item.children else None
                if node is None or not hasattr(node, "data") or node.data == "func_def":
                    continue
                try:
                    interpreter.transform(item)
                except VisitError as e:
                    raise unwrap_visit_error(e)

    except RuntimeError as e:
        print(f"{filename}: {e}")
        sys.exit(1)


def runviperfile(filepath: str):
    path = Path(filepath)

    if not path.exists():
        print(f"VP: Error occurred, File not found: {filepath}")
        return

    if path.suffix != ".vp":
        print(f"VP: Error occurred, Expected a .vp file, received: {path.suffix}")
        return

    sourcecode = path.read_text(encoding="utf-8")
    runsource(sourcecode, str(path))


def main():
    if len(sys.argv) < 2:
        print("Usage: python /Viper_interpreter/Viper/main.py <file.vp>")
        return

    runviperfile(sys.argv[1])


if __name__ == "__main__":
    main()