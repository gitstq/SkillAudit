# -*- coding: utf-8 -*-
"""Audit orchestration — wire discovery, rule sets, scoring into one result."""

from __future__ import annotations

import os
from typing import List, Optional

from .compat import check as compat_check
from .discovery import discover, load_package
from .model import AuditResult, SkillReport
from .rules_security import check as security_check
from .rules_spec import check as spec_check
from .scoring import score_package

#: Rule IDs understood by ``--include`` / ``--exclude``.
RULE_PREFIXES = {
    "SA": "规范",
    "SS": "安全",
    "SC": "兼容",
}

DEFAULT_ENABLED = ("spec", "security", "compat")


def audit_package(package, categories=None, min_severity=None):
    """Run all enabled rule groups against a single loaded package."""
    wanted = set(categories or DEFAULT_ENABLED)

    findings = []
    if "spec" in wanted:
        findings.extend(spec_check(package))
    if "security" in wanted:
        findings.extend(security_check(package))
    if "compat" in wanted:
        findings.extend(compat_check(package))

    findings = _sort_findings(findings)
    if min_severity:
        findings = _filter_min_severity(findings, min_severity)

    score, grade, stats = score_package(package, findings)
    return SkillReport(package=package, findings=findings, score=score,
                       grade=grade, stats=stats)


def audit_path(path, categories=None, min_severity=None, limit=None):
    """Discover every skill under ``path`` and audit each one."""
    packages = discover(path) if limit is None else discover(path, limit=limit)
    reports = [audit_package(pkg, categories, min_severity) for pkg in packages]
    reports.sort(key=lambda r: (r.score, r.name.lower()))
    return AuditResult(reports=reports, scan_root=os.path.abspath(path))


def audit_single(directory, categories=None, min_severity=None):
    """Audit exactly one skill directory (no recursion)."""
    package = load_package(directory, scan_root=os.path.dirname(
        os.path.abspath(directory)), read_script_contents=True)
    report = audit_package(package, categories, min_severity)
    return AuditResult(reports=[report], scan_root=os.path.abspath(directory))


def _sort_findings(findings):
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted(findings, key=lambda f: (order.get(f.severity, 3), f.rule_id,
                                           f.file or "", f.line))


def _filter_min_severity(findings, min_severity):
    rank = {"info": 0, "warning": 1, "error": 2}
    threshold = rank.get(str(min_severity).lower(), 0)
    return [f for f in findings if rank.get(f.severity, 0) >= threshold]


def filter_by_rule(result, include=None, exclude=None):
    """Post-filter an :class:`AuditResult` by rule-id prefix lists."""
    if not include and not exclude:
        return result
    include = tuple(p.upper() for p in (include or []))
    exclude = tuple(p.upper() for p in (exclude or []))

    for report in result.reports:
        kept = []
        for finding in report.findings:
            hit = False
            if include:
                hit = not any(finding.rule_id.startswith(p) for p in include)
            if exclude:
                hit = hit or any(finding.rule_id.startswith(p) for p in exclude)
            if not hit:
                kept.append(finding)
        report.findings = kept
        score, grade, stats = score_package(report.package, kept)
        report.score = score
        report.grade = grade
        report.stats = stats
    return result
