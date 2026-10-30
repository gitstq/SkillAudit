# -*- coding: utf-8 -*-
"""Deterministic 0-100 scoring for a skill package.

Scoring is deliberately **transparent**: a reviewer can reproduce the number by
hand from the finding list. We start from a perfect score, debit per finding
according to severity, apply a few structural bonuses/penalties that the rules
already emitted, and floor at zero.

Why cap certain losses? Without a cap a sloppy ``README.md.bak`` with two dozen
``info`` findings would tank a genuinely clean package. Severity-level caps keep
the signal meaningful.
"""

from __future__ import annotations

#: Points deducted per finding, per severity.
WEIGHTS = {
    "error": 15,
    "warning": 5,
    "info": 1,
}

#: Maximum total deduction contributed by each severity bucket.
CAPS = {
    "error": 60,
    "warning": 25,
    "info": 8,
}

#: Additional penalty when core front-matter fields are missing outright.
MISSING_CORE_RULES = ("SA003", "SA010", "SA020")
MISSING_CORE_PENALTY = 10

GRADE_BANDS = (
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (0, "E"),
)

GRADE_COMMENT = {
    "A": "规范严谨，可直接分发",
    "B": "质量良好，少量建议项",
    "C": "基本可用，建议整改",
    "D": "存在明显缺陷，需修订",
    "E": "不建议使用，存在高风险或缺失核心字段",
}


def grade_for(score):
    for threshold, label in GRADE_BANDS:
        if score >= threshold:
            return label
    return "E"


def build_stats(package, findings):
    """Collect the inventory numbers shown alongside the score."""
    manifest = package.manifest or {}
    body = getattr(package, "manifest_body", "") or ""
    return {
        "manifest_keys": len(manifest),
        "body_lines": len(body.splitlines()),
        "scripts": len(package.script_paths),
        "references": len(package.reference_paths),
        "assets": len(package.asset_paths),
        "extra_files": len(package.extra_files),
        "has_front_matter": bool(getattr(package, "has_front_matter", False)),
    }


def score_package(package, findings):
    """Return ``(score, grade, stats)`` for one audited package."""
    total = 100

    per_bucket = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        per_bucket[finding.severity] = per_bucket.get(finding.severity, 0) + WEIGHTS.get(
            finding.severity, 1)

    for severity, raw in per_bucket.items():
        total -= min(raw, CAPS.get(severity, raw))

    rule_ids = {f.rule_id for f in findings}
    missing_core = len(rule_ids.intersection(MISSING_CORE_RULES))
    if missing_core:
        total -= MISSING_CORE_PENALTY * missing_core

    if not getattr(package, "has_front_matter", False):
        total -= 10

    total = max(0, min(100, int(round(total))))
    stats = build_stats(package, findings)
    stats["comments"] = GRADE_COMMENT[grade_for(total)]
    return total, grade_for(total), stats
