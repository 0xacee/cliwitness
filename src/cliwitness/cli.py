"""CliWitness command-line interface."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from . import __version__
from .report import json_report, junit_report, text_report
from .runner import run_spec
from .spec import load_spec


TEMPLATE = '''version = 1
command = ["{python}", "path/to/your_cli.py"]
timeout = 5
max_output_bytes = 65536
normalize_newlines = true
inherit_env = ["PATH"]

[[cases]]
name = "prints version"
args = ["--version"]

[cases.expect]
exit = 0
stdout_matches = ["^your-cli [0-9]+\\\\.[0-9]+"]
stderr_exact = ""
'''


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="cliwitness", description="Declarative black-box CLI contracts")
    root.add_argument("--version", action="version", version=__version__)
    subcommands = root.add_subparsers(dest="command")
    run = subcommands.add_parser("run", help="run a TOML contract suite")
    run.add_argument("spec", nargs="?", default="cliwitness.toml")
    run.add_argument("--format", choices=("text", "json", "junit"), default="text")
    run.add_argument("--jobs", type=int, default=1)
    initialize = subcommands.add_parser("init", help="create a starter cliwitness.toml")
    initialize.add_argument("path", nargs="?", default="cliwitness.toml")
    return root


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command is None:
        parser().print_help()
        return 0
    try:
        if arguments.command == "init":
            target = Path(arguments.path)
            with target.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(TEMPLATE)
            print(f"Created {target}")
            return 0
        spec = load_spec(arguments.spec)
        results = run_spec(spec, arguments.jobs)
        render = {"text": text_report, "json": json_report, "junit": junit_report}[arguments.format]
        sys.stdout.write(render(results))
        return 0 if all(result.passed for result in results) else 1
    except (OSError, RuntimeError, ValueError) as error:
        print(f"cliwitness: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
