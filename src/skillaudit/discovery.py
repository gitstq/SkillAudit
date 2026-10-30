# -*- coding: utf-8 -*-
"""Skill package discovery.

A *skill package* is a directory containing a ``SKILL.md``. SkillAudit never
assumes a single vendor layout: Claude Code, Codex CLI, Cursor, CodeBuddy,
Windsurf and friends all invented slightly different homes for skills, and
people scatter them across dot-directories, project folders and monorepos.

Discovery therefore walks a tree, recognises known installation roots, and
labels each hit with the platform it most likely belongs to.
"""

from __future__ import annotations

import os
from typing import Dict, Generator, List, Optional

from .model import SkillPackage
from .yamlmini import YamlMiniError, extract_front_matter

#: File name that marks the root of a skill package.
MANIFEST_NAME = "SKILL.md"

#: Directories never worth walking into.
SKIP_DIRS = frozenset((
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".idea",
    ".vscode", ".next", ".nuxt", "coverage", ".gradle", "vendor",
))

#: Recognised installation roots → platform label.
PLATFORM_ROOTS = (
    ((".claude", "skills"), "Claude Code"),
    ((".claude", "plugins"), "Claude Code"),
    ((".codex", "skills"), "Codex CLI"),
    ((".cursor", "skills"), "Cursor"),
    ((".codebuddy", "skills"), "CodeBuddy"),
    ((".windsurf", "skills"), "Windsurf"),
    ((".github", "skills"), "GitHub Copilot"),
    ((".agents",), "Generic Agent"),
    (("skills",), "Generic Agent"),
)

#: Extensions treated as executable support scripts.
SCRIPT_SUFFIXES = frozenset((
    ".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".rb",
    ".pl", ".php", ".ps1", ".bat", ".cmd", ".go", ".rs",
))

#: Directories carrying reference material / binary assets.
REFERENCE_DIRS = ("references", "reference", "docs", "resources")
ASSET_DIRS = ("assets", "asset", "templates", "static", "files")

#: Hard cap so a pathological tree cannot hang the audit.
MAX_DEPTH = 8
MAX_PACKAGES = 500


def _relpath(path, root):
    try:
        rel = os.path.relpath(path, root)
    except ValueError:  # pragma: no cover - different drives on Windows
        return path
    return rel.replace(os.sep, "/")


def detect_platform(path, scan_root=None):
    """Infer the most likely platform from the package location."""
    norm = (path or "").replace(os.sep, "/").lower()
    for parts, label in PLATFORM_ROOTS:
        joined = "/".join(parts)
        if joined and joined in norm:
            return label
    return None


def is_skill_dir(path):
    return os.path.isfile(os.path.join(path, MANIFEST_NAME))


def iter_skill_dirs(root, max_depth=MAX_DEPTH):
    """Yield every directory that contains a ``SKILL.md`` beneath ``root``."""
    root = os.path.abspath(root)
    if os.path.isfile(root):
        parent = os.path.dirname(root)
        if os.path.basename(root).upper() == MANIFEST_NAME:
            yield parent
        return

    if not os.path.isdir(root):
        return

    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        if depth >= max_depth:
            dirnames[:] = []
        if MANIFEST_NAME in filenames:
            yield dirpath


def read_text(path):
    """Read a UTF-8 text file defensively (skills ship weird encodings)."""
    with open(path, "rb") as handle:
        raw = handle.read()
    for encoding in ("utf-8", "utf-8-sig", "gbk", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_package(path, scan_root=None, read_script_contents=False):
    """Build a :class:`SkillPackage` from a skill directory."""
    path = os.path.abspath(path)
    manifest_path = os.path.join(path, MANIFEST_NAME)
    manifest = None
    manifest_lines = []
    body_offset = 0
    manifest_body = ""
    manifest_error = None

    if os.path.isfile(manifest_path):
        try:
            text = read_text(manifest_path)
            parsed, body, skipped = extract_front_matter(text)
            manifest = parsed or {}
            manifest_body = body
            # Keep raw lines around so rules can point at exact source positions.
            manifest_lines = text.splitlines()
            body_offset = skipped
        except YamlMiniError as exc:
            manifest = None
            manifest_error = str(exc)

    package = SkillPackage(
        root=path,
        manifest=manifest or {},
        manifest_path=manifest_path if os.path.isfile(manifest_path) else None,
        platform=detect_platform(path, scan_root),
    )
    package.manifest_body = manifest_body
    package.manifest_error = manifest_error
    package.has_front_matter = manifest is not None and bool(manifest)
    package.manifest_lines = manifest_lines
    package.body_offset = body_offset

    script_paths = []
    reference_paths = []
    asset_paths = []
    extra_files = []

    for dirpath, dirnames, filenames in os.walk(path):
        rel_dir = os.path.relpath(dirpath, path)
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        top_parts = rel_dir.replace(os.sep, "/").split("/") if rel_dir != "." else []
        for filename in sorted(filenames):
            full = os.path.join(dirpath, filename)
            rel = _relpath(full, path)
            suffix = os.path.splitext(filename)[1].lower()
            if suffix in SCRIPT_SUFFIXES:
                script_paths.append(rel)
            elif top_parts and top_parts[0] in REFERENCE_DIRS:
                reference_paths.append(rel)
            elif top_parts and top_parts[0] in ASSET_DIRS:
                asset_paths.append(rel)
            elif rel.upper() == MANIFEST_NAME:
                continue
            else:
                extra_files.append(rel)

    package.script_paths = script_paths
    package.reference_paths = reference_paths
    package.asset_paths = asset_paths
    package.extra_files = extra_files
    package.script_contents = {}

    if read_script_contents:
        for rel in script_paths:
            full = os.path.join(path, rel)
            try:
                package.script_contents[rel] = read_text(full)
            except OSError:
                package.script_contents[rel] = ""

    return package


def discover(root, limit=MAX_PACKAGES):
    """Discover every skill package under ``root``.

    When ``root`` itself is a skill directory it is returned alone, which makes
    ``skillaudit audit ./my-skill`` behave the way users expect.
    """
    root = os.path.abspath(root)
    packages = []
    if is_skill_dir(root):
        packages.append(load_package(root, scan_root=os.path.dirname(root),
                                     read_script_contents=True))
        return packages

    for directory in iter_skill_dirs(root):
        try:
            packages.append(load_package(directory, scan_root=root,
                                        read_script_contents=True))
        except OSError:
            continue
        if len(packages) >= limit:
            break
    return packages
