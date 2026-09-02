# CliWitness

[![CI](https://github.com/0xacee/cliwitness/actions/workflows/ci.yml/badge.svg)](https://github.com/0xacee/cliwitness/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab.svg)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-7c3aed.svg)](LICENSE)

**Executable contracts for the interface users actually touch.**

CliWitness runs a command as an argument vector—never through a shell—and
checks exit codes, stdout, stderr, JSON, regexes, timeouts, and output bounds
from a reviewable TOML file.

```text
$ cliwitness run examples/cliwitness.toml --jobs 2
PASS  human greeting (31 ms)
PASS  machine greeting (34 ms)

2/2 CLI contracts passed
```

Unit tests can prove internal functions. CliWitness proves the installed
program's public process boundary: parsing, streams, exit semantics, and
deadline behavior together.

## Quick start

Python 3.11 or newer is required. Runtime dependencies: zero.

```bash
python -m pip install \
  https://github.com/0xacee/cliwitness/releases/download/v0.1.0/cliwitness-0.1.0-py3-none-any.whl

cliwitness init
cliwitness run
cliwitness run --format junit > cli-results.xml
```

## Contract format

```toml
#:schema https://raw.githubusercontent.com/0xacee/cliwitness/main/schemas/cliwitness.schema.json

version = 1
command = ["{python}", "src/my_cli.py"]
timeout = 5
max_output_bytes = 65536
inherit_env = ["PATH"]

[[cases]]
name = "returns structured status"
args = ["status", "--json"]
env = { NO_COLOR = "1" }

[cases.expect]
exit = 0
stdout_contains = ["ready"]
stdout_excludes = ["token"]
stdout_matches = ["^\\{"]
stderr_exact = ""
json_equals = { status = "ready" }
```

`{python}` expands to the interpreter running CliWitness. Paths and working
directories resolve from the spec file, so the same contract works from any
checkout location.

## Assertions

| Field | Meaning |
| --- | --- |
| `exit` | exact child exit code; defaults to `0` |
| `timed_out` | whether the deadline must be reached |
| `stdout_exact`, `stderr_exact` | complete stream equality |
| `*_contains`, `*_excludes` | literal substring checks |
| `*_matches` | Python regular expressions, multiline mode |
| `json_equals` | parsed stdout must deeply equal the TOML value |

Cases run sequentially by default. `--jobs N` runs them concurrently while
preserving declaration order in every report.

## Isolation and safety

- Commands are arrays passed to `subprocess.Popen` with `shell=False`.
- Child environments start empty except names explicitly listed in
  `inherit_env`; minimum Windows process variables are retained on Windows.
- Captured streams are drained to prevent deadlocks but retained only up to
  `max_output_bytes` per stream.
- A timeout kills the child and remains an explicit, assertable outcome.
- Failure diagnostics describe mismatches without echoing captured output.

Specs are executable test intent. Review them like code and never commit real
secrets in `env`, arguments, stdin, or expected output.

The optional `#:schema` directive enables completion and validation in editors
that understand TOML schema comments.

## Reports and exit codes

Text is optimized for humans, JSON for custom automation, and JUnit XML for CI
test viewers.

| Code | Meaning |
| ---: | --- |
| `0` | every contract passed |
| `1` | one or more contract assertions failed |
| `2` | invalid spec, usage, process startup, or I/O failure |

## License

MIT
