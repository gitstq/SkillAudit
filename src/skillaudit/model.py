# -*- coding: utf-8 -*-
"""Core data models for SkillAudit.

All models are plain Python objects with ``to_dict()`` so that any renderer
(text / JSON / SARIF) can consume them without extra plumbing.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

# --------------------------------------------------------------------------
# Severity / Category vocabularies
# --------------------------------------------------------------------------

#: Severity levels ordered from most to least critical.
SEVERITY_ORDER = ("error", "warning", "info")

SEVERITY_ALIAS = {
    "error": "error",
    "errors": "error",
    "critical": "error",
    "high": "error",
    "warning": "warning",
    "warn": "warning",
    "medium": "warning",
    "info": "info",
    "low": "info",
    "note": "info",
}


def normalize_severity(value):
    """Map a loose severity string onto one of :data:`SEVERITY_ORDER`."""
    key = str(value or "info").strip().lower()
    return SEVERITY_ALIAS.get(key, "info")


#: Logical grouping of rules — drives both filtering and reporting.
CATEGORIES = ("spec", "security", "compat", "quality")

CATEGORY_LABELS = {
    "spec": "规范",
    "security": "安全",
    "compat": "兼容",
    "quality": "质量",
}


class Finding(object):
    """A single issue discovered while auditing a skill package."""

    __slots__ = ("rule_id", "title", "severity", "category", "file", "line",
                 "message", "fix", "evidence")

    def __init__(self, rule_id, title, severity="info", category="spec",
                 file=None, line=0, message="", fix="", evidence=None):
        self.rule_id = rule_id
        self.title = title
        self.severity = normalize_severity(severity)
        self.category = category if category in CATEGORIES else "quality"
        self.file = file
        self.line = int(line or 0)
        self.message = message
        self.fix = fix
        self.evidence = evidence

    @property
    def location(self):
        """Human readable ``path:line`` reference."""
        if not self.file:
            return "-"
        if self.line:
            return "%s:%d" % (self.file, self.line)
        return self.file

    def to_dict(self):
        data = {
            "rule_id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "fix": self.fix,
        }
        if self.file:
            data["file"] = self.file
        if self.line:
            data["line"] = self.line
        if self.evidence:
            data["evidence"] = self.evidence
        return data

    def __repr__(self):  # pragma: no cover - debugging helper
        return "<Finding %s %s %s>" % (self.rule_id, self.severity, self.location)


class SkillPackage(object):
    """Raw material harvested from a skill directory before rule evaluation."""

    def __init__(self, root, manifest=None, manifest_path=None, script_paths=None,
                 reference_paths=None, asset_paths=None, extra_files=None,
                 platform=None):
        self.root = root
        self.manifest = manifest or {}
        self.manifest_path = manifest_path
        self.script_paths = script_paths or []
        self.reference_paths = reference_paths or []
        self.asset_paths = asset_paths or []
        self.extra_files = extra_files or []
        self.platform = platform

    @property
    def name(self):
        value = self.manifest.get("name")
        if value:
            return str(value)
        return os.path.basename(os.path.normpath(self.root)) or os.path.normpath(self.root)

    def to_dict(self):
        return {
            "root": self.root,
            "name": self.name,
            "platform": self.platform,
            "manifest_path": self.manifest_path,
            "script_count": len(self.script_paths),
            "reference_count": len(self.reference_paths),
            "asset_count": len(self.asset_paths),
        }


class SkillReport(object):
    """Audit result for exactly one skill package."""

    def __init__(self, package, findings=None, score=0, grade="?", stats=None):
        self.package = package
        self.findings = findings or []
        self.score = score
        self.grade = grade
        self.stats = stats or {}

    # -- convenience ------------------------------------------------------
    @property
    def name(self):
        return self.package.name

    @property
    def root(self):
        return self.package.root

    def count(self, severity):
        return sum(1 for f in self.findings if f.severity == severity)

    @property
    def error_count(self):
        return self.count("error")

    @property
    def warning_count(self):
        return self.count("warning")

    @property
    def info_count(self):
        return self.count("info")

    @property
    def passed(self):
        return self.error_count == 0

    def filtered(self, severities=None, categories=None):
        sev = set(severities or ()) if severities else None
        cat = set(categories or ()) if categories else None
        out = []
        for item in self.findings:
            if sev and item.severity not in sev:
                continue
            if cat and item.category not in cat:
                continue
            out.append(item)
        return out

    def rules_hit(self):
        seen = {}
        for item in self.findings:
            seen.setdefault(item.rule_id, 0)
            seen[item.rule_id] += 1
        return seen

    def to_dict(self):
        return {
            "name": self.name,
            "root": self.root,
            "platform": self.package.platform,
            "score": self.score,
            "grade": self.grade,
            "passed": self.passed,
            "counts": {
                "error": self.error_count,
                "warning": self.warning_count,
                "info": self.info_count,
                "total": len(self.findings),
            },
            "stats": self.stats,
            "findings": [f.to_dict() for f in self.findings],
        }


class AuditResult(object):
    """Aggregate result across one or more skill packages."""

    def __init__(self, reports=None, scan_root=None):
        self.reports = reports or []
        self.scan_root = scan_root

    @property
    def total(self):
        return len(self.reports)

    @property
    def passed_count(self):
        return sum(1 for r in self.reports if r.passed)

    @property
    def failed_count(self):
        return self.total - self.passed_count

    @property
    def error_count(self):
        return sum(r.error_count for r in self.reports)

    @property
    def warning_count(self):
        return sum(r.warning_count for r in self.reports)

    @property
    def info_count(self):
        return sum(r.info_count for r in self.reports)

    @property
    def average_score(self):
        if not self.reports:
            return 0.0
        return round(sum(r.score for r in self.reports) / float(len(self.reports)), 1)

    @property
    def exit_code(self):
        """``0`` clean, ``1`` errors present, ``2`` only warnings."""
        if not self.reports:
            return 1
        if self.error_count:
            return 1
        if self.warning_count:
            return 2
        return 0

    def all_findings(self):
        out = []
        for report in self.reports:
            out.extend(report.findings)
        return out

    def to_dict(self):
        return {
            "scan_root": self.scan_root,
            "summary": {
                "total": self.total,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "errors": self.error_count,
                "warnings": self.warning_count,
                "infos": self.info_count,
                "average_score": self.average_score,
            },
            "reports": [r.to_dict() for r in self.reports],
        }
