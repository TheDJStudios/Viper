from pathlib import Path

from lark import Lark


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
         | collect_stmt
         | call_stmt
         | if_stmt
         | try_stmt

print_stmt: "print" "(" expr ")" ";"
var_stmt: "$" NAME ":" type "=" expr ";"
assign_stmt: "$" NAME "=" expr ";"
return_stmt: "return" expr ";"
collect_stmt: "collect" "(" expr? ")" ";"
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

?atom: FSTRING    -> fstring
     | SSTRING    -> string
     | CHAR       -> char
     | STRING     -> string
     | NUMBER     -> number
     | "true"     -> true
     | "false"    -> false
     | "none"     -> none_literal
     | "collect" "(" expr? ")" -> collect
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

FSTRING: /#"(?:\\.|[^"\\])*"/
SSTRING: /'(?:\\.|[^'\\]){2,}'|''/
CHAR: /'(?:\\.|[^'\\])'/
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


class ViperLanguageError(RuntimeError):
    pass


parser = Lark(VIPER_GRAMMAR, parser="lalr")


def parse_source(source_code, filename, error_cls=ViperLanguageError):
    try:
        return parser.parse(source_code)
    except Exception as error:
        raise error_cls(f"{filename}: VP: Parse error\n    {error}") from error


def extract_string(token):
    text = str(token)
    return text[1:-1]


def resolve_import_path(raw_path, importer_path):
    if raw_path.startswith("/"):
        return Path(raw_path).resolve()

    if importer_path == Path("<stdin>"):
        base_dir = Path.cwd()
    else:
        base_dir = importer_path.parent

    return (base_dir / raw_path).resolve()


def get_type_name(type_node, error_cls=ViperLanguageError):
    type_name = TYPE_NAME_MAP.get(type_node.data)
    if type_name is None:
        raise error_cls(f"VP: Error, Unknown type '{type_node.data}'")
    return type_name


def _source_key(path):
    if path == Path("<stdin>"):
        return path
    return path.resolve()


def collect_program(root_path, source_code=None, error_cls=ViperLanguageError):
    root_path = Path(root_path)

    if root_path == Path("<stdin>"):
        if source_code is None:
            raise error_cls("VP: Error, Missing source code for <stdin>")
        root_source = source_code
        root_tree = parse_source(root_source, "<stdin>", error_cls)
    else:
        root_path = root_path.resolve()
        root_source = root_path.read_text(encoding="utf-8") if source_code is None else source_code
        root_tree = parse_source(root_source, str(root_path), error_cls)

    functions = {}
    loaded_files = set()
    active_files = set()

    def visit(tree, current_path):
        current_path = Path(current_path)
        current_key = _source_key(current_path)

        if current_key in active_files:
            raise error_cls(f"VP: Error, Circular import detected for '{current_key}'")

        if current_key in loaded_files:
            return

        active_files.add(current_key)

        for item in tree.children:
            child = item.children[0]

            if child.data == "import_stmt":
                import_target = extract_string(child.children[0])
                import_path = resolve_import_path(import_target, current_path)

                if not import_path.exists():
                    raise error_cls(f"VP: Error, Imported file not found: {import_target}")

                import_tree = parse_source(import_path.read_text(encoding="utf-8"), str(import_path), error_cls)
                visit(import_tree, import_path)

            elif child.data == "func_def":
                ret_type = get_type_name(child.children[0], error_cls)
                name = str(child.children[1])

                if name in functions:
                    raise error_cls(
                        f"VP: Error, Function '{name}' already defined in '{functions[name]['source']}'"
                    )

                functions[name] = {
                    "name": name,
                    "ret_type": ret_type,
                    "body": child.children[2],
                    "source": str(current_key),
                }

        active_files.remove(current_key)
        loaded_files.add(current_key)

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
