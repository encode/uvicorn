import argparse
import subprocess
import sys
from pathlib import Path


def get_usage_lines() -> list:
    res = subprocess.run(["uvicorn", "--help"], stdout=subprocess.PIPE)
    help_text = res.stdout.decode("utf-8")
    return ["$ uvicorn --help", *help_text.splitlines()]


def generate(path: Path, check: bool = False) -> None:
    content = path.read_text()

    lines = content.splitlines()
    marker_lineno = lines.index("<!-- gen_cli_usage:marker -->")
    assert lines[marker_lineno + 1] == "```"
    start = marker_lineno + 2
    end = next(
        lineno for lineno, line in enumerate(lines[start:], start) if line == "```"
    )
    lines = lines[:start] + get_usage_lines() + lines[end:]

    output = "\n".join(lines) + "\n"

    if check:
        if content == output:
            rv = 0
        else:
            print(
                "ERROR: CLI usage in index.md is out of sync. "
                "Run scripts/lint to fix."
            )
            rv = 1
        sys.exit(rv)

    path.write_text(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path in (Path("docs", "index.md"), Path("docs", "deployment.md")):
        generate(path, check=args.check)
