from pathlib import Path
import tempfile
import textwrap
import unittest

from cliwitness.spec import load_spec


class SpecTests(unittest.TestCase):
    def write(self, content: str) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="cliwitness-spec-"))
        target = directory / "cliwitness.toml"
        target.write_text(textwrap.dedent(content), encoding="utf-8")
        return target

    def test_loads_a_minimal_spec_with_safe_defaults(self) -> None:
        spec = load_spec(self.write('''
            version = 1
            command = ["{python}", "tool.py"]
            [[cases]]
            name = "version"
            args = ["--version"]
        '''))
        self.assertEqual(spec.timeout, 5.0)
        self.assertEqual(spec.max_output_bytes, 65_536)
        self.assertTrue(spec.normalize_newlines)
        self.assertEqual(spec.cases[0].expect.exit, 0)

    def test_rejects_duplicate_case_names(self) -> None:
        target = self.write('''
            version = 1
            command = ["tool"]
            [[cases]]
            name = "same"
            [[cases]]
            name = "same"
        ''')
        with self.assertRaisesRegex(ValueError, "duplicate case name"):
            load_spec(target)

    def test_rejects_invalid_regular_expressions_while_loading(self) -> None:
        target = self.write('''
            version = 1
            command = ["tool"]
            [[cases]]
            name = "bad regex"
            [cases.expect]
            stdout_matches = ["["]
        ''')
        with self.assertRaisesRegex(ValueError, "invalid regex"):
            load_spec(target)

    def test_rejects_unknown_fields(self) -> None:
        target = self.write('''
            version = 1
            command = ["tool"]
            mystery = true
            [[cases]]
            name = "case"
        ''')
        with self.assertRaisesRegex(ValueError, "unknown field"):
            load_spec(target)


if __name__ == "__main__":
    unittest.main()
