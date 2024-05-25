"""
Look for a marker comment in docs pages, and place the output of
`$ uvicorn --help` there. Pass `--check` to ensure the content is in sync.
"""
import argparse
import subprocess
import sys
import typing
from pathlib import Path


def _get_usage_lines() -> typing.List[str]:
    res = subprocess.run(["uvicorn", "--help"], stdout=subprocess.PIPE)
    help_text = res.stdout.decode("utf-8")
    return ["```", "$ uvicorn --help", *help_text.splitlines(), "```"]


def _find_next_codefence_lineno(lines: typing.List[str], after: int) -> int:
    return next(lineno for lineno, line in enumerate(lines[after:], after) if line == "```")


def _get_insert_location(lines: typing.List[str]) -> typing.Tuple[int, int]:
    marker = lines.index("<!-- :cli_usage: -->")
    start = marker + 1

    if lines[start] == "```":
        # Already generated.
        # <!-- :cli_usage: -->
        # ```   <- start
        # [...]
        # ```   <- end
        next_codefence = _find_next_codefence_lineno(lines, after=start + 1)
        end = next_codefence + 1
    else:
        # Not generated yet.
        end = start

    return start, end


def _generate_cli_usage(path: Path, check: bool = False) -> int:
    content = path.read_text()

    lines = content.splitlines()
    usage_lines = _get_usage_lines()
    start, end = _get_insert_location(lines)
    lines = lines[:start] + usage_lines + lines[end:]
    output = "\n".join(lines) + "\n"

    if check:
        if content == output:
            return 0
        print(f"ERROR: CLI usage in {path} is out of sync. Run scripts/lint to fix.")
        return 1

    path.write_text(output)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    paths = [Path("docs", "index.md"), Path("docs", "deployment.md")]
    rv = 0
    for path in paths:
        rv |= _generate_cli_usage(path, check=args.check)
    sys.exit(rv)
