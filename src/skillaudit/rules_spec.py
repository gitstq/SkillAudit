# -*- coding: utf-8 -*-
"""Specification rules — does the manifest follow the Agent Skills contract?

The checks below mirror constraints that every mainstream agent runtime agrees
on (skill name syntax, directory layout, required front-matter keys, resource
referencing, progressive-disclosure sizing). Anything a given vendor treats as
optional degrades to ``warning`` or ``info`` instead of ``error``.
"""

from __future__ import annotations

import os
import re
from typing import List

from .model import Finding

RULESET = "spec"

#: ``name`` must be lowercase letters / digits / single hyphens.
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

#: Agents refuse names longer than this.
MAX_NAME_LEN = 64

#: Recommended description bounds used by the big runtimes.
DESC_MIN = 20
DESC_MAX = 1024

#: A monolithic SKILL.md defeats progressive disclosure.
BODY_MAX_LINES = 500
BODY_SOFT_LINES = 300

#: Allowed top-level keys plus widely adopted extras.
KNOWN_KEYS = frozenset((
    "name", "description", "license", "allowed-tools", "allowed_tools",
    "allowedTools", "version", "metadata", "author", "tags", "homepage",
    "compatibility", "disable-model-invocation", "user-invocable",
))

RESERVED_DIRS = frozenset(("scripts", "references", "assets"))

#: Markdown link targets we can validate locally.
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def check(package) -> List[Finding]:
    """Run every specification rule against ``package``."""
    findings = []
    findings.extend(_manifest_rules(package))
    findings.extend(_body_rules(package))
    findings.extend(_layout_rules(package))
    findings.extend(_reference_rules(package))
    return findings


# --------------------------------------------------------------------------
# Front matter
# --------------------------------------------------------------------------

def _manifest_rules(package):
    out = []
    rel_name = os.path.basename(os.path.normpath(package.root))
    manifest_path = package.manifest_path

    if manifest_path and not os.path.isfile(manifest_path):
        out.append(Finding(
            "SA001", "缺少 SKILL.md 清单文件", severity="error", category=RULESET,
            file=rel_name, message="技能包根目录未找到 SKILL.md，无法被任何 Agent 运行时识别。",
            fix="在根目录新建 SKILL.md，并在文件顶部写入 YAML front matter。"))
        return out

    if package.manifest_error:
        out.append(Finding(
            "SA002", "front matter 解析失败", severity="error", category=RULESET,
            file=_rel(package, manifest_path), line=1,
            message="YAML front matter 无法解析：%s" % package.manifest_error,
            fix="检查缩进是否统一使用空格、是否存在未加引号的特殊字符。"))
        return out

    if not package.has_front_matter:
        out.append(Finding(
            "SA003", "缺少 YAML front matter", severity="error", category=RULESET,
            file=_rel(package, manifest_path), line=1,
            message="SKILL.md 顶部未检测到以 --- 包裹的 YAML front matter。",
            fix="在文件首行插入 ---，写入 name 与 description，再用 --- 闭合。"))
        return out

    manifest = package.manifest or {}
    raw_name = manifest.get("name")
    raw_desc = manifest.get("description")
    name_line = _key_line(package, "name")
    desc_line = _key_line(package, "description")

    # --- name -----------------------------------------------------------
    if not raw_name:
        out.append(Finding(
            "SA010", "front matter 缺少 name", severity="error", category=RULESET,
            file=_rel(package, manifest_path), line=1,
            message="未提供 name 字段，运行时无法注册该技能。",
            fix="添加 name: my-skill（仅小写字母、数字与连字符）。"))
    else:
        name = str(raw_name).strip()
        if not NAME_RE.match(name):
            out.append(Finding(
                "SA011", "name 命名不规范", severity="error", category=RULESET,
                file=_rel(package, manifest_path), line=name_line,
                message="name=%r 不符合规范。" % name,
                fix="仅使用小写字母、数字与连字符，且不能以连字符开头或结尾。"))
        if len(name) > MAX_NAME_LEN:
            out.append(Finding(
                "SA012", "name 过长", severity="error", category=RULESET,
                file=_rel(package, manifest_path), line=name_line,
                message="name 长度 %d 超过上限 %d。" % (len(name), MAX_NAME_LEN),
                fix="缩短名称，保持在 %d 字符以内。" % MAX_NAME_LEN))
        if name != rel_name and rel_name not in ("", ".", "..", os.sep):
            out.append(Finding(
                "SA013", "name 与目录名不一致", severity="warning", category=RULESET,
                file=_rel(package, manifest_path), line=name_line,
                message="front matter name=%r，而目录名为 %r。" % (name, rel_name),
                fix="建议让二者保持一致，避免多平台加载时产生歧义。"))
        if name.startswith("claude") or name.startswith("anthropic"):
            out.append(Finding(
                "SA014", "name 使用保留前缀", severity="warning", category=RULESET,
                file=_rel(package, manifest_path), line=name_line,
                message="name 以 claude/anthropic 开头，可能被运行时保留。",
                fix="改用业务含义明确的前缀。"))

    # --- description ----------------------------------------------------
    if not raw_desc:
        out.append(Finding(
            "SA020", "front matter 缺少 description", severity="error", category=RULESET,
            file=_rel(package, manifest_path), line=1,
            message="未提供 description，Agent 无法判断何时调用该技能。",
            fix="用一句话写清「做什么」与「什么时候用」，例如：Extract text from PDF files. Use when the user asks about PDF content."))
    else:
        desc = " ".join(str(raw_desc).split())
        if len(desc) < DESC_MIN:
            out.append(Finding(
                "SA021", "description 过短", severity="warning", category=RULESET,
                file=_rel(package, manifest_path), line=desc_line,
                message="description 仅 %d 字符，触发条件描述不足。" % len(desc),
                fix="补充触发场景描述，至少 %d 字符。" % DESC_MIN))
        elif len(desc) > DESC_MAX:
            out.append(Finding(
                "SA022", "description 过长", severity="warning", category=RULESET,
                file=_rel(package, manifest_path), line=desc_line,
                message="description 达 %d 字符，超出推荐上限 %d。" % (len(desc), DESC_MAX),
                fix="把细节移入正文，description 仅保留用途与触发时机。"))
        if len(desc) > 40 and desc.isascii() and not re.search(
                r"\b(use|when|used|for)\b", desc, re.I):
            out.append(Finding(
                "SA023", "description 缺少触发条件", severity="info", category=RULESET,
                file=_rel(package, manifest_path), line=desc_line,
                message="description 未出现 Use when / Use for 等触发提示词。",
                fix="追加形如「Use when the user asks ...」的触发描述。"))

    # --- unknown / misspelled keys --------------------------------------
    for key in manifest:
        if str(key).lower().replace("_", "-") not in KNOWN_KEYS:
            out.append(Finding(
                "SA030", "存在未知 front matter 字段", severity="info", category=RULESET,
                file=_rel(package, manifest_path), line=_key_line(package, key),
                message="未知字段：%s" % key,
                fix="移除该字段，或确认其为自定义扩展并做好文档说明。"))

    if "description" in manifest and isinstance(manifest.get("description"), (list, dict)):
        out.append(Finding(
            "SA024", "description 结构错误", severity="error", category=RULESET,
            file=_rel(package, manifest_path), line=desc_line,
            message="description 必须是字符串，当前为 %s。" % type(manifest.get("description")).__name__,
            fix="改为单行字符串，或用 >- 折叠块标量。"))

    return out


# --------------------------------------------------------------------------
# Markdown body
# --------------------------------------------------------------------------

def _body_rules(package):
    out = []
    body = getattr(package, "manifest_body", "") or ""
    rel = _rel(package, package.manifest_path)

    if not body.strip():
        out.append(Finding(
            "SA040", "SKILL.md 正文为空", severity="error", category=RULESET,
            file=rel, message="front matter 之后没有任何正文内容。",
            fix="补充操作步骤、示例与注意事项。"))
        return out

    lines = body.splitlines()
    if len(lines) > BODY_MAX_LINES:
        out.append(Finding(
            "SA041", "SKILL.md 正文过长", severity="error", category=RULESET,
            file=rel,
            message="正文 %d 行，超过 %d 行上限。" % (len(lines), BODY_MAX_LINES),
            fix="将细节拆分到 references/ 子文件，正文仅保留主流程。"))
    elif len(lines) > BODY_SOFT_LINES:
        out.append(Finding(
            "SA042", "SKILL.md 正文偏长", severity="warning", category=RULESET,
            file=rel,
            message="正文 %d 行，建议控制在 %d 行以内。" % (len(lines), BODY_SOFT_LINES),
            fix="考虑渐进式披露：正文放主流程，细则移入 references/。"))

    headings = [l for l in lines if l.lstrip().startswith("#")]
    if len(headings) < 2:
        out.append(Finding(
            "SA043", "正文缺少结构化小节", severity="warning", category=RULESET,
            file=rel, message="仅检测到 %d 个标题，可读性不足。" % len(headings),
            fix="用 ## 划分「用途 / 使用步骤 / 示例 / 注意事项」等小节。"))

    fence_open = sum(1 for l in lines if l.strip().startswith("```"))
    if fence_open % 2 != 0:
        out.append(Finding(
            "SA044", "代码块围栏未闭合", severity="warning", category=RULESET,
            file=rel, message="``` 代码块数量为奇数（%d），存在未闭合围栏。" % fence_open,
            fix="补齐缺失的 ``` 结束围栏。"))

    if not re.search(r"(python|bash|sh|```)", body, re.I):
        out.append(Finding(
            "SA045", "缺少可执行示例", severity="info", category=RULESET,
            file=rel, message="正文未检测到命令或代码示例。",
            fix="补一条可直接复制运行的命令或代码片段。"))

    return out


# --------------------------------------------------------------------------
# Directory layout
# --------------------------------------------------------------------------

def _layout_rules(package):
    out = []
    rel_root = os.path.basename(os.path.normpath(package.root)) or package.root

    stray = [p for p in package.extra_files
             if p.upper() == "README.MD" or p.upper() == "SKILL.MD.BAK"]
    for item in stray:
        out.append(Finding(
            "SA050", "存在冗余文件", severity="info", category=RULESET,
            file=item, message="技能包内的 %s 不会被运行时加载。" % item,
            fix="删除该文件，或移入 references/ 目录。"))

    total = (len(package.script_paths) + len(package.reference_paths)
             + len(package.asset_paths) + len(package.extra_files))
    if total > 40:
        out.append(Finding(
            "SA051", "技能包文件过多", severity="warning", category=RULESET,
            file=rel_root, message="技能包包含 %d 个附加文件，建议拆分。" % total,
            fix="拆成多个单一职责的技能包。"))

    deep = [p for p in (package.reference_paths + package.asset_paths
                        + package.script_paths) if p.count("/") > 2]
    if deep:
        out.append(Finding(
            "SA052", "资源嵌套层级过深", severity="info", category=RULESET,
            file=deep[0], message="%d 个资源嵌套超过 2 层。" % len(deep),
            fix="扁平化目录结构，控制在 scripts/ references/ assets/ 之下。"))

    return out


# --------------------------------------------------------------------------
# Reference / link integrity
# --------------------------------------------------------------------------

def _reference_rules(package):
    out = []
    body = getattr(package, "manifest_body", "") or ""
    rel = _rel(package, package.manifest_path)

    referenced = set()
    for target in LINK_RE.findall(body):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        referenced.add(target.split("#")[0])

    for target in sorted(referenced):
        candidate = os.path.join(package.root, target.replace("/", os.sep))
        if not os.path.exists(candidate):
            out.append(Finding(
                "SA060", "正文引用了不存在的资源", severity="error", category=RULESET,
                file=rel, message="链接目标 %s 在技能包内不存在。" % target,
                fix="补齐该文件或修正链接路径。"))

    for rel_path in package.reference_paths:
        name = os.path.basename(rel_path)
        if body and name not in body:
            out.append(Finding(
                "SA061", "references 文件未被引用", severity="info", category=RULESET,
                file=rel_path,
                message="SKILL.md 正文中未出现 %s 的链接。" % name,
                fix="在正文中引用它，或删除该冗余文件。"))

    return out


# --------------------------------------------------------------------------

def _rel(package, path):
    """Render ``path`` relative to the package root for readable output."""
    if not path:
        return os.path.basename(os.path.normpath(package.root)) or package.root
    try:
        rel = os.path.relpath(path, package.root)
    except ValueError:  # pragma: no cover
        return path
    return rel.replace(os.sep, "/")


def _key_line(package, key):
    """Locate the 1-based line number of a front-matter ``key``.

    Falls back to ``1`` when the manifest cannot be located line-wise, so a
    reviewer always gets a clickable position instead of nothing.
    """
    lines = getattr(package, "manifest_lines", None) or []
    needle = str(key).lower()
    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith(("#", "-", "---")):
            continue
        if ":" not in stripped:
            continue
        head = stripped.split(":", 1)[0].strip().lower()
        if head == needle:
            return index
    return 1


def _body_offset(package):
    """Number of source lines consumed by the delimiters before the prose."""
    return int(getattr(package, "body_offset", 0) or 0)
