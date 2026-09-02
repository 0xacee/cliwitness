from pathlib import Path
import tempfile
import textwrap
import unittest

from cliwitness.runner import run_spec
from cliwitness.spec import load_spec


FIXTURE = Path(__file__).with_name("fixture_cli.py").resolve()


class RunnerTests(unittest.TestCase):
    def spec(self, cases: str, *, timeout: float = 2, max_output: int = 65536):
        directory = Path(tempfile.mkdtemp(prefix="cliwitness-run-"))
        target = directory / "suite.toml"
        target.write_text(textwrap.dedent(f'''
            version = 1
            command = ["{{python}}", "{FIXTURE.as_posix()}"]
            timeout = {timeout}
            max_output_bytes = {max_output}
            {cases}
        '''), encoding="utf-8")
        return load_spec(target)

    def test_evaluates_exit_stream_regex_and_json_contracts_in_parallel(self) -> None:
        spec = self.spec('''
            [[cases]]
            name = "echo"
            args = ["echo", "hello"]
            [cases.expect]
            stdout_exact = "hello"
            stderr_exact = ""

            [[cases]]
            name = "structured"
            args = ["json", "proof"]
            [cases.expect]
            stdout_matches = ["\\\"ok\\\": true"]
            json_equals = { ok = true, value = "proof" }

            [[cases]]
            name = "expected failure"
            args = ["fail", "broken"]
            [cases.expect]
            exit = 7
            stderr_contains = ["broken"]
        ''')
        results = run_spec(spec, jobs=3)
        self.assertEqual([result.name for result in results], ["echo", "structured", "expected failure"])
        self.assertTrue(all(result.passed for result in results))

    def test_timeout_is_an_assertable_outcome(self) -> None:
        spec = self.spec('''
            [[cases]]
            name = "deadline"
            args = ["sleep", "0.2"]
            [cases.expect]
            timed_out = true
        ''', timeout=0.05)
        result = run_spec(spec)[0]
        self.assertTrue(result.passed)
        self.assertTrue(result.timed_out)

    def test_output_is_drained_but_memory_capture_is_bounded(self) -> None:
        spec = self.spec('''
            [[cases]]
            name = "bounded"
            args = ["flood", "4096"]
        ''', max_output=1024)
        result = run_spec(spec)[0]
        self.assertFalse(result.passed)
        self.assertTrue(result.stdout.truncated)
        self.assertEqual(len(result.stdout.text.encode()), 1024)
        self.assertEqual(result.stdout.bytes, 4096)

    def test_mismatch_diagnostics_do_not_dump_captured_output(self) -> None:
        spec = self.spec('''
            [[cases]]
            name = "redacted diagnostic"
            args = ["echo", "sensitive-value"]
            [cases.expect]
            stdout_contains = ["public-marker"]
        ''')
        result = run_spec(spec)[0]
        self.assertFalse(result.passed)
        self.assertNotIn("sensitive-value", " ".join(result.failures))


if __name__ == "__main__":
    unittest.main()
