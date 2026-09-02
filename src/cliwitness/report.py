"""Deterministic text, JSON, and JUnit reports."""

from __future__ import annotations

import json
from xml.etree import ElementTree

from .runner import CaseResult


def text_report(results: tuple[CaseResult, ...]) -> str:
    lines: list[str] = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"{status}  {result.name} ({result.duration_ms} ms)")
        for failure in result.failures:
            lines.append(f"      {failure}")
    passed = sum(result.passed for result in results)
    lines.append("")
    lines.append(f"{passed}/{len(results)} CLI contracts passed")
    return "\n".join(lines) + "\n"


def json_report(results: tuple[CaseResult, ...]) -> str:
    payload = {
        "schemaVersion": 1,
        "passed": all(result.passed for result in results),
        "cases": [result.to_dict() for result in results],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def junit_report(results: tuple[CaseResult, ...]) -> str:
    suite = ElementTree.Element("testsuite", {
        "name": "cliwitness",
        "tests": str(len(results)),
        "failures": str(sum(not result.passed for result in results)),
        "time": f"{sum(result.duration_ms for result in results) / 1000:.3f}",
    })
    for result in results:
        case = ElementTree.SubElement(suite, "testcase", {
            "name": result.name,
            "time": f"{result.duration_ms / 1000:.3f}",
        })
        if not result.passed:
            failure = ElementTree.SubElement(case, "failure", {"message": result.failures[0]})
            failure.text = "\n".join(result.failures)
        if result.stdout.text:
            ElementTree.SubElement(case, "system-out").text = result.stdout.text
        if result.stderr.text:
            ElementTree.SubElement(case, "system-err").text = result.stderr.text
    return ElementTree.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"
