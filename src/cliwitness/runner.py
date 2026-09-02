"""Run CLI cases without a shell and evaluate their observable contract."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Thread
import time

from .spec import Case, Spec


@dataclass(frozen=True)
class StreamCapture:
    text: str
    bytes: int
    truncated: bool


@dataclass(frozen=True)
class CaseResult:
    name: str
    passed: bool
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: StreamCapture
    stderr: StreamCapture
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class _BoundedReader:
    def __init__(self, stream, limit: int) -> None:
        self.stream = stream
        self.limit = limit
        self.parts: list[bytes] = []
        self.total = 0
        self.kept = 0

    def read(self) -> None:
        while chunk := self.stream.read(8192):
            self.total += len(chunk)
            if self.kept < self.limit:
                retained = chunk[: self.limit - self.kept]
                self.parts.append(retained)
                self.kept += len(retained)

    def capture(self) -> StreamCapture:
        content = b"".join(self.parts).decode("utf-8", errors="replace")
        return StreamCapture(content, self.total, self.total > self.limit)


def _expand(values: tuple[str, ...]) -> list[str]:
    return [value.replace("{python}", sys.executable) for value in values]


def _environment(spec: Spec, case: Case) -> dict[str, str]:
    environment = {name: os.environ[name] for name in spec.inherit_env if name in os.environ}
    if os.name == "nt":
        for name in ("SYSTEMROOT", "COMSPEC", "PATHEXT", "WINDIR"):
            if name in os.environ:
                environment.setdefault(name, os.environ[name])
    environment.update({"NO_COLOR": "1", "PYTHONIOENCODING": "utf-8"})
    environment.update(case.env)
    return environment


def _evaluate(case: Case, exit_code: int | None, timed_out: bool, stdout: str, stderr: str) -> tuple[str, ...]:
    expect = case.expect
    failures: list[str] = []
    if timed_out != expect.timed_out:
        failures.append(f"timed_out expected {expect.timed_out}, got {timed_out}")
    if not timed_out and exit_code != expect.exit:
        failures.append(f"exit expected {expect.exit}, got {exit_code}")
    for label, actual, exact in (("stdout", stdout, expect.stdout_exact), ("stderr", stderr, expect.stderr_exact)):
        if exact is not None and actual != exact:
            failures.append(f"{label} did not exactly match")
    for label, actual, needles in (("stdout", stdout, expect.stdout_contains), ("stderr", stderr, expect.stderr_contains)):
        for needle in needles:
            if needle not in actual:
                failures.append(f"{label} did not contain {needle!r}")
    for label, actual, needles in (("stdout", stdout, expect.stdout_excludes), ("stderr", stderr, expect.stderr_excludes)):
        for needle in needles:
            if needle in actual:
                failures.append(f"{label} unexpectedly contained {needle!r}")
    for label, actual, patterns in (("stdout", stdout, expect.stdout_matches), ("stderr", stderr, expect.stderr_matches)):
        for pattern in patterns:
            if re.search(pattern, actual, flags=re.MULTILINE) is None:
                failures.append(f"{label} did not match /{pattern}/")
    if expect.has_json_equals:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as error:
            failures.append(f"stdout was not valid JSON: {error.msg}")
        else:
            if parsed != expect.json_equals:
                failures.append("stdout JSON did not equal expected value")
    return tuple(failures)


def run_case(spec: Spec, case: Case) -> CaseResult:
    command = [*_expand(spec.command), *_expand(case.args)]
    cwd = (spec.path.parent / case.cwd).resolve()
    if not cwd.is_dir():
        raise ValueError(f"case {case.name!r} cwd is not a directory: {cwd}")
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=_environment(spec, case),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as error:
        raise RuntimeError(f"case {case.name!r} could not start {command[0]!r}: {error.strerror}") from error
    assert process.stdin and process.stdout and process.stderr
    stdout_reader = _BoundedReader(process.stdout, spec.max_output_bytes)
    stderr_reader = _BoundedReader(process.stderr, spec.max_output_bytes)
    threads = [Thread(target=stdout_reader.read), Thread(target=stderr_reader.read)]
    for thread in threads:
        thread.start()
    try:
        process.stdin.write(case.stdin.encode("utf-8"))
        process.stdin.close()
        process.wait(timeout=spec.timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        timed_out = True
    finally:
        for thread in threads:
            thread.join()
        process.stdout.close()
        process.stderr.close()
    elapsed = round((time.monotonic() - started) * 1000)
    stdout = stdout_reader.capture()
    stderr = stderr_reader.capture()
    failures = list(_evaluate(case, process.returncode, timed_out, stdout.text, stderr.text))
    if stdout.truncated:
        failures.append(f"stdout exceeded max_output_bytes ({stdout.bytes} bytes)")
    if stderr.truncated:
        failures.append(f"stderr exceeded max_output_bytes ({stderr.bytes} bytes)")
    return CaseResult(case.name, not failures, process.returncode, timed_out, elapsed, stdout, stderr, tuple(failures))


def run_spec(spec: Spec, jobs: int = 1) -> tuple[CaseResult, ...]:
    if jobs < 1 or jobs > 64:
        raise ValueError("jobs must be between 1 and 64")
    if jobs == 1:
        return tuple(run_case(spec, case) for case in spec.cases)
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        return tuple(executor.map(lambda case: run_case(spec, case), spec.cases))
