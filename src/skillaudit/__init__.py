# -*- coding: utf-8 -*-
"""SkillAudit — Agent Skills (SKILL.md) specification & security audit engine.

Zero third-party dependencies · offline · CLI + Python library.

Quick library use::

    from skillaudit import audit_path, render_text
    result = audit_path("./.claude/skills")
    print(render_text(result))
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "SkillAudit contributors"
__license__ = "MIT"
__all__ = [
    "__version__",
    "audit_path",
    "audit_single",
    "audit_package",
    "discover",
    "load_package",
    "render_text",
    "render_json",
    "render_sarif",
    "Finding",
    "SkillPackage",
    "SkillReport",
    "AuditResult",
]

from .audit import audit_package, audit_path, audit_single, filter_by_rule
from .discovery import discover, load_package, read_text
from .model import AuditResult, Finding, SkillPackage, SkillReport
from .render import render_json, render_sarif, render_text
from .scoring import grade_for

_DEFAULT = [None]  # placeholder to keep import order explicit
