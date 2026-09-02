import json
from xml.etree import ElementTree
import unittest

from cliwitness.report import json_report, junit_report, text_report
from cliwitness.runner import CaseResult, StreamCapture


class ReportTests(unittest.TestCase):
    def result(self, passed: bool) -> CaseResult:
        return CaseResult(
            name="escapes <xml>",
            passed=passed,
            exit_code=0 if passed else 1,
            timed_out=False,
            duration_ms=12,
            stdout=StreamCapture("hello", 5, False),
            stderr=StreamCapture("", 0, False),
            failures=() if passed else ("expected <zero>",),
        )

    def test_json_report_is_machine_readable(self) -> None:
        payload = json.loads(json_report((self.result(True),)))
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["cases"][0]["stdout"]["bytes"], 5)

    def test_junit_report_escapes_names_and_failures(self) -> None:
        root = ElementTree.fromstring(junit_report((self.result(False),)))
        self.assertEqual(root.attrib["failures"], "1")
        self.assertEqual(root.find("testcase").attrib["name"], "escapes <xml>")

    def test_text_report_has_a_compact_summary(self) -> None:
        self.assertIn("1/1 CLI contracts passed", text_report((self.result(True),)))


if __name__ == "__main__":
    unittest.main()
