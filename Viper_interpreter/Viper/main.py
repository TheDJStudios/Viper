#!/bin/python3
import sys
from pathlib import Path


def runviperfile(filepath: str):
    path = Path(filepath)

    if not path.exists():
        print(f"VP: Error occurred, File not found: {filepath}")
        return

    if path.suffix != ".vp":
        print(f"VP: Error occurred, Expected a .vp file, received: {path.suffix}")
        return
    sourcecode = path.read_text(encoding="utf-8")
    # put function to run the source code here
    runsource(sourcecode, str(path))

def runsource(source_code: str, filename: str = "<stdin>"):
    lines = source_code.splitlines()

    for line_number, line in enumerate(lines, start=1):
        line = line.strip()

        if not line:
            continue
        # comments
        if line.startswith("%"):
            continue

        if line.startswith("print(") and line.endswith(");"):
            value = line[len("print("):-2]
            value = value.strip()

            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

            print(value)
        else:
            print(f"{filename}:{line_number}: VP: Error, Unknown statement")
            print(f"    {line}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python /Viper_interpreter/Viper/main.py <file.vp>")
        return

    runviperfile(sys.argv[1])

if __name__ == "__main__":
    main()
