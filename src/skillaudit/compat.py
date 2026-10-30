# -*- coding: utf-8 -*-
"""Cross-platform compatibility checks.

A skill that works in Claude Code may silently fail in Codex CLI, Cursor or
CodeBuddy: front-matter keys are not uniformly supported, file discovery rules
differ, and executable scripts need different affordances per platform.
These rules surface the friction points before a user tries to install it.
"""

from __future__ import annotations

import os
import stat
from typing import List

from .model import Finding

RULESET = "compat"

#: Keys only understood by Claude Code.
CLAUDE_ONLY = ("disable-model-invocation", "user-invocable", "argument-hint")

#: Aliases that carry the same meaning across runtimes.
ALLOWED_TOOLS_KEYS = ("allowed-tools", "allowed_tools", "allowedTools")

SHEBANG_PREFIX = "#!"


def check(package) -> List[Finding]:
    findings = []
    findings.extend(_front_matter_compat(package))
    findings.extend(_script_compat(package))
    findings.extend(_install_compat(package))
    return findings


def _front_matter_compat(package):
    out = []
    manifest = package.manifest or {}
    rel = _md_rel(package)

    if not manifest:
        return out

    tool_keys = [k for k in manifest if str(k).lower() in ALLOWED_TOOLS_KEYS]
    if len(tool_keys) > 1:
        out.append(Finding(
            "SC001", "allowed-tools 字段重复定义", severity="warning", category=RULESET,
            file=rel, message="同时定义了 %s。" % "、".join(sorted(tool_keys)),
            fix="仅保留目标平台支持的那一种写法。"))

    for key in tool_keys:
        value = manifest.get(key)
        if isinstance(value, str) and (" " in value.strip() or "," in value):
            out.append(Finding(
                "SC002", "allowed-tools 为空格分隔字符串", severity="info", category=RULESET,
                file=rel,
                message="%s 使用空格/逗号分隔的字符串写法（Claude Code 传统格式）。" % key,
                fix="若需兼容 Codex CLI 等新运行时，建议改为 YAML 列表。"))
        elif isinstance(value, list):
            unknown = [v for v in value
                       if not str(v).replace("_", "").replace("-", "").isalnum()]
            if unknown:
                out.append(Finding(
                    "SC003", "allowed-tools 含非法条目", severity="warning", category=RULESET,
                    file=rel, message="存在无法识别的工具名：%s" % ", ".join(map(str, unknown[:5])),
                    fix="使用 Bash / Read / Write / Glob / Grep 等标准工具名。"))

    claude_keys = [k for k in manifest if str(k).lower() in CLAUDE_ONLY]
    if claude_keys:
        out.append(Finding(
            "SC004", "使用了 Claude Code 专有字段", severity="info", category=RULESET,
            file=rel,
            message="字段 %s 仅在 Claude Code 生效。" % "、".join(map(str, claude_keys)),
            fix="其它运行时会忽略这些字段，请在 README 中说明平台要求。"))

    if "license" not in manifest:
        out.append(Finding(
            "SC005", "未声明 license 字段", severity="info", category=RULESET,
            file=rel, message="front matter 缺少 license，分发时权利边界不清。",
            fix="添加 license: MIT（或其它符合你意图的许可证标识）。"))

    version = manifest.get("version")
    if version is not None and not str(version).strip():
        out.append(Finding(
            "SC006", "version 字段为空", severity="info", category=RULESET,
            file=rel, message="version 已声明但取值为空。",
            fix="填入语义化版本号，例如 1.0.0。"))

    return out


def _script_compat(package):
    out = []
    for rel_path in sorted(package.script_paths):
        full = os.path.join(package.root, rel_path)
        suffix = os.path.splitext(rel_path)[1].lower()

        if suffix in (".sh", ".bash", ".zsh", ".py", ".js", ".rb", ".pl"):
            if full in (None,) or not os.path.isfile(full):
                continue
            try:
                with open(full, "rb") as handle:
                    head = handle.read(256)
            except OSError:
                continue
            text = head.decode("utf-8", errors="replace")
            if not text.startswith(SHEBANG_PREFIX):
                out.append(Finding(
                    "SC010", "脚本缺少 shebang 声明", severity="warning", category=RULESET,
                    file=rel_path,
                    message="首行没有 #! 解释器声明，跨平台直接执行时会失败。",
                    fix="首行加入 #!/usr/bin/env python3 或 #!/usr/bin/env bash。"))

        if suffix in (".sh", ".bash", ".zsh") and os.name == "posix":
            try:
                mode = os.stat(full).st_mode
            except OSError:
                continue
            if not (mode & stat.S_IXUSR):
                out.append(Finding(
                    "SC011", "Shell 脚本缺少可执行权限", severity="info", category=RULESET,
                    file=rel_path,
                    message="文件未设置可执行位，chmod +x 之前无法直接调用。",
                    fix="提交前执行 chmod +x %s。" % rel_path))

        if suffix == ".ps1":
            out.append(Finding(
                "SC012", "PowerShell 脚本跨平台受限", severity="info", category=RULESET,
                file=rel_path,
                message=".ps1 脚本在 macOS / Linux 上默认不可用。",
                fix="提供同功能的 .sh 或 Python 版本以提升可移植性。"))

    return out


def _install_compat(package):
    out = []
    if package.platform is None:
        out.append(Finding(
            "SC020", "未位于标准安装目录", severity="info", category=RULESET,
            file=os.path.basename(os.path.normpath(package.root)) or package.root,
            message="该技能不在已知安装根目录下，需手动安装才会被发现。",
            fix="放入 .claude/skills/、.codex/skills/ 或 .codebuddy/skills/ 等标准路径。"))

    has_docs = bool(package.reference_paths)
    if not has_docs and len((getattr(package, "manifest_body", "") or "").splitlines()) > 200:
        out.append(Finding(
            "SC021", "长正文未拆分到 references", severity="warning", category=RULESET,
            file=_md_rel(package),
            message="SKILL.md 较长且没有 references/ 目录，加载成本偏高。",
            fix="把可选细节移入 references/，正文只保留触发路径。"))

    return out


def _md_rel(package):
    if not package.manifest_path:
        return "SKILL.md"
    try:
        return os.path.relpath(package.manifest_path, package.root).replace(os.sep, "/")
    except ValueError:  # pragma: no cover
        return "SKILL.md"
