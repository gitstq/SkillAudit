# -*- coding: utf-8 -*-
"""End-to-end tests for the CLI, renderers and result filters."""

# pylint: disable=missing-docstring
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from skillaudit.audit import audit_single, filter_by_rule  # noqa: E402
from skillaudit.render import render_json, render_sarif, render_text  # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples")
GOOD = os.path.join(EXAMPLES, "skills", "csv-insight")
BAD = os.path.join(EXAMPLES, "bad-skill")


def run_cli(*args, expect=None):
    """Invoke ``python -m skillaudit`` and return ``(returncode, stdout, stderr)``."""
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC
    env["NO_COLOR"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "skillaudit"] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=ROOT,
    )
    out, err = proc.communicate(timeout=90)
    text = out.decode("utf-8", "replace")
    error_text = err.decode("utf-8", "replace")
    if expect is not None:
        assert proc.returncode == expect, (
            "exit %d != %d\n%s\n%s" % (proc.returncode, expect, text, error_text))
    return proc.returncode, text, error_text


class RendererTests(unittest.TestCase):
    def test_json_shape(self):
        result = audit_single(BAD)
        payload = json.loads(render_json(result))
        self.assertIn("summary", payload)
        self.assertIn("reports", payload)
        self.assertEqual(payload["summary"]["total"], 1)
        report = payload["reports"][0]
        self.assertIn("score", report)
        self.assertIn("grade", report)
        self.assertIn("findings", report)
        self.assertIsInstance(report["findings"], list)

    def test_json_is_serialisable_for_clean_and_dirty(self):
        for path in (GOOD, BAD):
            json.loads(render_json(audit_single(path)))

    def test_sarif_shape(self):
        payload = json.loads(render_sarif(audit_single(BAD)))
        self.assertEqual(payload["version"], "2.1.0")
        run_block = payload["runs"][0]
        self.assertIn("tool", run_block)
        self.assertIn("results", run_block)
        driver = run_block["tool"]["driver"]
        self.assertTrue(driver["rules"])
        for rule in driver["rules"]:
            self.assertIn("id", rule)
            self.assertIn("shortDescription", rule)
        for item in run_block["results"]:
            self.assertIn("ruleId", item)
            self.assertIn("level", item)
            self.assertIn("locations", item)

    def test_sarif_rule_ids_cover_findings(self):
        result = audit_single(BAD)
        payload = json.loads(render_sarif(result))
        declared = {r["id"] for r in payload["runs"][0]["tool"]["driver"]["rules"]}
        emitted = {f.rule_id for f in result.all_findings()}
        self.assertTrue(emitted.issubset(declared))

    def test_text_contains_key_sections(self):
        rendered = render_text(audit_single(BAD))
        self.assertIn("SkillAudit", rendered)
        self.assertIn("总览", rendered)
        self.assertIn("退出码", rendered)

    def test_text_without_reports(self):
        from skillaudit.model import AuditResult
        rendered = render_text(AuditResult(reports=[], scan_root="/tmp"))
        self.assertIn("未发现任何技能包", rendered)

    def test_color_disabled_outside_tty(self):
        rendered = render_text(audit_single(BAD))
        self.assertNotIn("\033[", rendered)


class FilterTests(unittest.TestCase):
    def test_exclude_removes_findings(self):
        result = filter_by_rule(audit_single(BAD), exclude=["SC"])
        remaining = {f.rule_id for f in result.all_findings()}
        self.assertTrue(remaining)
        self.assertFalse([rid for rid in remaining if rid.startswith("SC")])

    def test_include_narrows_findings(self):
        result = filter_by_rule(audit_single(BAD), include=["SS"])
        remaining = {f.rule_id for f in result.all_findings()}
        self.assertTrue(remaining)
        for rid in remaining:
            self.assertTrue(rid.startswith("SS"), rid)

    def test_score_recomputed_after_filter(self):
        full = audit_single(BAD)
        trimmed = filter_by_rule(audit_single(BAD), include=["SS"])
        self.assertGreaterEqual(trimmed.reports[0].score, full.reports[0].score)


class CliTests(unittest.TestCase):
    def test_version(self):
        code, out, _ = run_cli("--version", expect=0)
        self.assertIn("skaudit", out)

    def test_help(self):
        code, out, _ = run_cli("--help", expect=0)
        self.assertIn("audit", out)

    def test_audit_text_output(self):
        code, out, _ = run_cli("audit", BAD, "--no-banner", expect=1)
        self.assertIn("SkillAudit", out)
        self.assertIn("退出码", out)

    def test_audit_json_output(self):
        code, out, _ = run_cli("audit", BAD, "-f", "json", expect=1)
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["total"], 1)

    def test_audit_sarif_output(self):
        code, out, _ = run_cli("audit", BAD, "-f", "sarif", expect=1)
        payload = json.loads(out)
        self.assertEqual(payload["version"], "2.1.0")

    def test_clean_skill_exits_zero(self):
        run_cli("audit", os.path.join(EXAMPLES, "skills"), "--no-banner", expect=0)

    def test_fail_on_none_always_zero(self):
        run_cli("audit", BAD, "--fail-on", "none", "--no-banner", expect=0)

    def test_missing_path_errors(self):
        run_cli("audit", "/definitely/not/here", expect=1)

    def test_output_to_file(self):
        tmp = tempfile.mkdtemp(prefix="sa-cli-")
        try:
            target = os.path.join(tmp, "report.json")
            run_cli("audit", BAD, "-f", "json", "-o", target, expect=1)
            with open(target, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["summary"]["total"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_list_command(self):
        code, out, _ = run_cli("list", EXAMPLES, expect=0)
        self.assertIn("csv-insight", out)

    def test_list_json(self):
        code, out, _ = run_cli("list", EXAMPLES, "--json", expect=0)
        payload = json.loads(out)
        names = [p["name"] for p in payload]
        self.assertIn("csv-insight", names)

    def test_rules_command_lists_all(self):
        code, out, _ = run_cli("rules", expect=0)
        self.assertIn("SS150", out)
        self.assertIn("SA020", out)
        self.assertIn("SC010", out)

    def test_rules_json(self):
        code, out, _ = run_cli("rules", "--json", expect=0)
        payload = json.loads(out)
        self.assertTrue(payload)
        for row in payload:
            self.assertIn("rule_id", row)

    def test_rules_filter(self):
        code, out, _ = run_cli("rules", "SS12", expect=0)
        self.assertIn("SS120", out)
        self.assertNotIn("SS110", out)

    def test_shorthand_path(self):
        code, out, _ = run_cli(BAD, "--no-banner", expect=1)
        self.assertIn("SkillAudit", out)

    def test_category_filter(self):
        code, out, _ = run_cli("audit", BAD, "-c", "spec", "-f", "json", expect=1)
        payload = json.loads(out)
        for finding in payload["reports"][0]["findings"]:
            self.assertEqual(finding["category"], "spec")

    def test_severity_filter(self):
        code, out, _ = run_cli(
            "audit", BAD, "-s", "error", "-f", "json", expect=1)
        payload = json.loads(out)
        for finding in payload["reports"][0]["findings"]:
            self.assertEqual(finding["severity"], "error")

    def test_quiet_mode(self):
        code, out, _ = run_cli("audit", BAD, "-q", expect=1)
        self.assertIn("E", out)
        self.assertNotIn("总览", out)


class ExampleIntegrityTests(unittest.TestCase):
    """Examples double as a regression suite for the whole pipeline."""

    def test_good_example_is_perfect(self):
        report = audit_single(GOOD).reports[0]
        self.assertEqual(report.score, 100)
        self.assertEqual(report.grade, "A")
        self.assertTrue(report.passed)
        self.assertEqual(report.findings, [])

    def test_bad_example_trips_injection_and_credentials(self):
        hit = audit_single(BAD).reports[0].rules_hit()
        for rule in ("SS150", "SS120", "SS122", "SS110", "SS100", "SA011"):
            self.assertIn(rule, hit, "expected %s in %s" % (rule, sorted(hit)))

    def test_bad_example_has_zero_trust_score(self):
        report = audit_single(BAD).reports[0]
        self.assertLessEqual(report.score, 30)
        self.assertEqual(report.grade, "E")

    def test_example_script_runs(self):
        script = os.path.join(GOOD, "scripts", "analyze.py")
        tmp = tempfile.mkdtemp(prefix="sa-example-")
        csv_path = os.path.join(tmp, "data.csv")
        with open(csv_path, "w", encoding="utf-8") as handle:
            handle.write("name,age,city\nalice,30,Beijing\nbob,,Shanghai\n")
        try:
            env = dict(os.environ)
            proc = subprocess.Popen(
                [sys.executable, script, "--file", csv_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            out, err = proc.communicate(timeout=60)
            self.assertEqual(proc.returncode, 0, err.decode())
            self.assertIn(b"name", out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
