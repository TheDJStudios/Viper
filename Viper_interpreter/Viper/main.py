import sys
from pathlib import Path
from lark import Lark, Transformer, v_args


VIPER_GRAMMAR = r"""
start: statement*

statement: print_stmt
         | var_stmt

print_stmt: "print" "(" expr ")" ";"
var_stmt: "$" NAME ":" type "=" expr ";"

type: "int"   -> int_type
    | "float" -> float_type
    | "str"   -> str_type
    | "bool"  -> bool_type

expr: STRING  -> string
    | NUMBER  -> number
    | "true"  -> true
    | "false" -> false
    | NAME    -> variable

%import common.CNAME -> NAME
%import common.ESCAPED_STRING -> STRING
%import common.NUMBER
%import common.WS
%ignore WS

COMMENT: /%[^\n]*/
%ignore COMMENT
"""


@v_args(inline=True)
class ViperInterpreter(Transformer):
    def __init__(self):
        super().__init__()
        self.variables = {}

    def string(self, token):
        text = str(token)
        return text[1:-1]

    def number(self, token):
        text = str(token)

        if "." in text:
            return float(text)

        return int(text)

    def true(self):
        return True

    def false(self):
        return False

    def variable(self, name):
        name = str(name)

        if name not in self.variables:
            raise RuntimeError(f"VP: Error, Unknown variable '{name}'")

        return self.variables[name]["value"]

    def int_type(self):
        return "int"

    def float_type(self):
        return "float"

    def str_type(self):
        return "str"

    def bool_type(self):
        return "bool"

    def value_matches_type(self, value, expected_type):
        if expected_type == "int":
            return isinstance(value, int) and not isinstance(value, bool)

        if expected_type == "float":
            return isinstance(value, float)

        if expected_type == "str":
            return isinstance(value, str)

        if expected_type == "bool":
            return isinstance(value, bool)

        return False

    def var_stmt(self, name, var_type, value):
        name = str(name)

        if name in self.variables:
            raise RuntimeError(f"VP: Error, Variable '{name}' already exists")

        if not self.value_matches_type(value, var_type):
            actual_type = type(value).__name__
            raise RuntimeError(
                f"VP: Error, Cannot assign {actual_type} to {var_type} variable '{name}'"
            )

        self.variables[name] = {
            "type": var_type,
            "value": value
        }

    def print_stmt(self, value):
        print(value)

    def statement(self, stmt):
        return stmt

    def start(self, *statements):
        return statements


parser = Lark(VIPER_GRAMMAR, parser="lalr")


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


def runsource(source_code: str, filename: str = "<stdin>"):
    try:
        tree = parser.parse(source_code)
        interpreter = ViperInterpreter()
        interpreter.transform(tree)

    except Exception as error:
        print(f"{filename}: VP: Error occurred while parsing/running source")
        print(f"    {error}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python /Viper_interpreter/Viper/main.py <file.vp>")
        return

    runviperfile(sys.argv[1])


if __name__ == "__main__":
    main()