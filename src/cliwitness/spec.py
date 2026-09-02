"""Load and validate CliWitness TOML specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import tomllib
from typing import Any


@dataclass(frozen=True)
class Expectation:
    exit: int = 0
    timed_out: bool = False
    stdout_exact: str | None = None
    stderr_exact: str | None = None
    stdout_contains: tuple[str, ...] = ()
    stderr_contains: tuple[str, ...] = ()
    stdout_excludes: tuple[str, ...] = ()
    stderr_excludes: tuple[str, ...] = ()
    stdout_matches: tuple[str, ...] = ()
    stderr_matches: tuple[str, ...] = ()
    json_equals: Any = field(default=None)
    has_json_equals: bool = False


@dataclass(frozen=True)
class Case:
    name: str
    args: tuple[str, ...]
    stdin: str
    env: dict[str, str]
    cwd: str
    expect: Expectation


@dataclass(frozen=True)
class Spec:
    path: Path
    command: tuple[str, ...]
    timeout: float
    max_output_bytes: int
    normalize_newlines: bool
    inherit_env: tuple[str, ...]
    cases: tuple[Case, ...]


def _reject_unknown(data: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValueError(f"{context} has unknown field(s): {', '.join(unknown)}")


def _strings(value: Any, context: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{context} must be an array of strings")
    if nonempty and not value:
        raise ValueError(f"{context} must not be empty")
    return tuple(value)


def _expectation(data: Any, context: str) -> Expectation:
    if not isinstance(data, dict):
        raise ValueError(f"{context} must be a table")
    allowed = {
        "exit", "timed_out", "stdout_exact", "stderr_exact", "stdout_contains",
        "stderr_contains", "stdout_excludes", "stderr_excludes", "stdout_matches",
        "stderr_matches", "json_equals",
    }
    _reject_unknown(data, allowed, context)
    exit_code = data.get("exit", 0)
    timed_out = data.get("timed_out", False)
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise ValueError(f"{context}.exit must be an integer")
    if not isinstance(timed_out, bool):
        raise ValueError(f"{context}.timed_out must be a boolean")
    for key in ("stdout_exact", "stderr_exact"):
        if key in data and not isinstance(data[key], str):
            raise ValueError(f"{context}.{key} must be a string")
    patterns = {}
    for key in ("stdout_contains", "stderr_contains", "stdout_excludes", "stderr_excludes", "stdout_matches", "stderr_matches"):
        patterns[key] = _strings(data.get(key, []), f"{context}.{key}")
    for key in ("stdout_matches", "stderr_matches"):
        for pattern in patterns[key]:
            try:
                re.compile(pattern)
            except re.error as error:
                raise ValueError(f"{context}.{key} has invalid regex {pattern!r}: {error}") from error
    return Expectation(
        exit=exit_code,
        timed_out=timed_out,
        stdout_exact=data.get("stdout_exact"),
        stderr_exact=data.get("stderr_exact"),
        json_equals=data.get("json_equals"),
        has_json_equals="json_equals" in data,
        **patterns,
    )


def load_spec(path: str | Path) -> Spec:
    target = Path(path).resolve()
    try:
        with target.open("rb") as handle:
            data = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"invalid TOML in {target}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError("specification must be a TOML table")
    _reject_unknown(data, {"version", "command", "timeout", "max_output_bytes", "normalize_newlines", "inherit_env", "cases"}, "specification")
    if data.get("version") != 1:
        raise ValueError("specification version must be 1")
    command = _strings(data.get("command"), "command", nonempty=True)
    timeout = data.get("timeout", 5.0)
    max_output = data.get("max_output_bytes", 65_536)
    normalize_newlines = data.get("normalize_newlines", True)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0 or timeout > 300:
        raise ValueError("timeout must be between 0 and 300 seconds")
    if not isinstance(max_output, int) or isinstance(max_output, bool) or not 1_024 <= max_output <= 16_777_216:
        raise ValueError("max_output_bytes must be between 1024 and 16777216")
    if not isinstance(normalize_newlines, bool):
        raise ValueError("normalize_newlines must be a boolean")
    inherit_env = _strings(data.get("inherit_env", ["PATH"]), "inherit_env")
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("cases must be a non-empty array of tables")
    cases: list[Case] = []
    names: set[str] = set()
    for index, raw in enumerate(raw_cases):
        context = f"cases[{index}]"
        if not isinstance(raw, dict):
            raise ValueError(f"{context} must be a table")
        _reject_unknown(raw, {"name", "args", "stdin", "env", "cwd", "expect"}, context)
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"{context}.name must be a non-empty string")
        if name in names:
            raise ValueError(f"duplicate case name: {name}")
        names.add(name)
        env = raw.get("env", {})
        if not isinstance(env, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in env.items()):
            raise ValueError(f"{context}.env must be a string-to-string table")
        stdin = raw.get("stdin", "")
        cwd = raw.get("cwd", ".")
        if not isinstance(stdin, str) or not isinstance(cwd, str):
            raise ValueError(f"{context}.stdin and {context}.cwd must be strings")
        cases.append(Case(
            name=name,
            args=_strings(raw.get("args", []), f"{context}.args"),
            stdin=stdin,
            env=dict(env),
            cwd=cwd,
            expect=_expectation(raw.get("expect", {}), f"{context}.expect"),
        ))
    return Spec(target, command, float(timeout), max_output, normalize_newlines, inherit_env, tuple(cases))
