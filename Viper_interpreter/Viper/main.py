#!/bin/python3
import sys
from pathlib import Path

# valid return types for function signatures
VALID_TYPES = {
    "int", "void", "float", "double", "string", "char",
    "char[]", "int[]", "float[]", "double[]", "string[]", "char[][]",
}


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


def parse_functions(lines: list, filename: str) -> dict:
    # first pass: hoist all function definitions into a dict keyed by name
    functions = {}
    i = 0

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if not line or line.startswith("%"):
            i += 1
            continue

        sig = try_parse_signature(line)
        if sig is None:
            i += 1
            continue

        ret_type, name = sig
        i += 1

        # handle brace on same line or next non-blank line
        body_start_line = i
        if "{" in lines[i - 1]:
            pass
        else:
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines) or lines[i].strip() != "{":
                print(f"{filename}: VP: Error, expected '{{' after function '{name}'")
                i += 1
                continue
            body_start_line = i + 1
            i += 1

        # collect body lines until closing brace
        body = []
        depth = 1
        while i < len(lines):
            bline = lines[i].strip()
            depth += bline.count("{") - bline.count("}")
            if depth <= 0:
                i += 1
                break
            body.append((i + 1, lines[i]))
            i += 1

        functions[name] = {"ret_type": ret_type, "body": body}

    return functions


def try_parse_signature(line: str):
    # matches: <type> <name>() { or <type> <name>()
    # handles array return types like int[]
    for t in sorted(VALID_TYPES, key=len, reverse=True):
        if line.startswith(t + " "):
            rest = line[len(t):].strip()
            # grab name before ()
            paren = rest.find("()")
            if paren == -1:
                continue
            name = rest[:paren].strip()
            if not name.isidentifier():
                continue
            return (t, name)
    return None


def runsource(source_code: str, filename: str = "<stdin>"):
    lines = source_code.splitlines()

    # hoist all functions first
    functions = parse_functions(lines, filename)

    vp_args = sys.argv[2:]
    builtins = {
        "$args": vp_args,
        "$argc": len(vp_args),
    }

    if "main" in functions:
        exit_code = execute_block(
            functions["main"]["body"], filename, builtins, functions
        )
        sys.exit(exit_code if isinstance(exit_code, int) else 0)
    else:
        # fallback: run top-level non-function lines
        toplevel = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line and not line.startswith("%") and try_parse_signature(line) is None:
                toplevel.append((i + 1, lines[i]))
            elif try_parse_signature(line) is not None:
                # skip over the whole function block
                while i < len(lines) and lines[i].strip() != "}":
                    i += 1
            i += 1
        execute_block(toplevel, filename, builtins, functions)


def resolve_value(token: str, builtins: dict, functions: dict, filename: str, line_number: int):
    token = token.strip()

    if token.startswith('"') and token.endswith('"'):
        return token[1:-1]

    if token in builtins:
        return builtins[token]

    # inline function call as argument
    if token.endswith("()"):
        name = token[:-2].strip()
        return call_function(name, filename, line_number, builtins, functions)

    # int literal
    try:
        return int(token)
    except ValueError:
        pass

    # float literal
    try:
        return float(token)
    except ValueError:
        pass

    print(f"{filename}:{line_number}: VP: Error, unknown value '{token}'")
    return None


def call_function(name: str, filename: str, line_number: int, builtins: dict, functions: dict):
    if name not in functions:
        print(f"{filename}:{line_number}: VP: Error, undefined function '{name}'")
        return None

    fn = functions[name]
    result = execute_block(fn["body"], filename, builtins, functions)

    # non-void functions must return something
    if fn["ret_type"] != "void" and result is None:
        print(f"{filename}:{line_number}: VP: Error, function '{name}' declared '{fn['ret_type']}' but did not return a value")

    return result


def execute_block(lines: list, filename: str, builtins: dict, functions: dict):
    for line_number, line in lines:
        line = line.strip()

        if not line or line.startswith("%"):
            continue

        # print() with arbitrary value/expression
        if line.startswith("print(") and line.endswith(");"):
            inner = line[len("print("):-2].strip()
            value = resolve_value(inner, builtins, functions, filename, line_number)
            if value is not None:
                print(value)
            continue

        # return statement
        if line.startswith("return ") and line.endswith(";"):
            val = line[len("return "):-1].strip()
            return resolve_value(val, builtins, functions, filename, line_number)

        # standalone function call
        if line.endswith("();"):
            name = line[:-3].strip()
            call_function(name, filename, line_number, builtins, functions)
            continue

        print(f"{filename}:{line_number}: VP: Error, Unknown statement")
        print(f"    {line}")

    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python /Viper_interpreter/Viper/main.py <file.vp>")
        return

    runviperfile(sys.argv[1])


if __name__ == "__main__":
    main()