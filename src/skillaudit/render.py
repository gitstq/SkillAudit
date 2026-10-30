# -*- coding: utf-8 -*-
"""Output renderers: human terminal report, JSON, SARIF 2.1.0.

Terminal output auto-disables ANSI colour when stdout is not a TTY or when
``NO_COLOR`` is set, so piping into a file always yields clean text.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List

from .model import SEVERITY_ORDER
from .rules_security import PATTERNS

# --------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------

_USE_COLOR = (sys.stdout.isatty() and not os.environ.get("NO_COLOR")
              and os.environ.get("TERM") not in (None, "dumb"))

_PALETTE = {
    "error": "\033[91m",
    "warning": "\033[93m",
    "info": "\033[96m",
    "ok": "\033[92m",
    "dim": "\033[90m",
    "bold": "\033[1m",
    "reset": "\033[0m",
}


def _paint(text, *styles):
    if not _USE_COLOR or not styles:
        return text
    codes = "".join(_PALETTE.get(s, "") for s in styles)
    return "%s%s%s" % (codes, text, _PALETTE["reset"])


SEVERITY_BADGE = {
    "error": "[ERROR]",
    "warning": "[WARN ]",
    "info": "[INFO ]",
}

SEVERITY_COLOR = {"error": "error", "warning": "warning", "info": "info"}


def _bar(score, width=20):
    filled = int(round(score / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


# --------------------------------------------------------------------------
# Terminal renderer
# --------------------------------------------------------------------------

def render_text(result, show_info=True, max_findings=None):
    """Render the full audit as a readable terminal report."""
    lines = []
    lines.append("")
    lines.append(_paint("🛡️  SkillAudit · 技能包规范与安全审计报告", "bold"))
    lines.append(_paint("    Agent Skills (SKILL.md) specification & security audit", "dim"))
    lines.append("")

    if not result.reports:
        lines.append(_paint("⚠️  未发现任何技能包（未找到包含 SKILL.md 的目录）。", "warning"))
        lines.append(_paint("    请确认路径正确，或使用 --single 直接指定技能目录。", "dim"))
        lines.append("")
        return "\n".join(lines)

    scan_root = result.scan_root or "."
    lines.append("📂 扫描路径：%s" % scan_root)
    lines.append("")

    _append_summary(lines, result)
    lines.append("")

    for index, report in enumerate(result.reports, start=1):
        _append_package(lines, index, report, show_info, max_findings)

    lines.append(_paint("─" * 68, "dim"))
    lines.append("")

    exit_code = result.exit_code
    if exit_code == 0:
        verdict = _paint("✅ 全部通过：未发现 error 或 warning 级问题。", "ok")
    elif exit_code == 1:
        verdict = _paint("❌ 未通过：存在 %d 个必须修复的 error 级问题。" % result.error_count,
                         "error")
    else:
        verdict = _paint("⚠️  通过但需关注：存在 %d 个 warning 级建议项。" % result.warning_count,
                         "warning")
    lines.append(verdict)
    lines.append(_paint("   退出码：%d（0=全部通过 / 1=存在错误 / 2=仅有告警）" % exit_code, "dim"))
    lines.append("")
    return "\n".join(lines)


def _append_summary(lines, result):
    lines.append(_paint("📊 总览", "bold"))
    lines.append("   技能包总数：%d   " % result.total
                 + _paint("通过 %d" % result.passed_count, "ok")
                 + "   "
                 + _paint("未通过 %d" % result.failed_count,
                          "error" if result.failed_count else "dim"))
    lines.append("   平均得分：%.1f / 100" % result.average_score)
    lines.append("   问题统计："
                 + _paint("error %d" % result.error_count,
                          "error" if result.error_count else "dim")
                 + " · "
                 + _paint("warning %d" % result.warning_count,
                          "warning" if result.warning_count else "dim")
                 + " · "
                 + _paint("info %d" % result.info_count, "dim"))
    lines.append("")
    lines.append("   %-32s %-6s %-6s %s" % ("技能包", "得分", "等级", "平台"))
    lines.append("   " + "─" * 64)
    for report in result.reports:
        lines.append("   %-32s %-6s %-6s %s" % (
            report.name[:32], report.score, report.grade,
            report.package.platform or "-"))


def _append_package(lines, index, report, show_info, max_findings):
    lines.append(_paint("─" * 68, "dim"))
    lines.append("")
    lines.append("%s %s   %s  %s" % (
        _paint("🔹", "bold"),
        _paint(report.name, "bold"),
        _paint("%s %d/100" % (_bar(report.score), report.score),
               "ok" if report.passed else "error"),
        _paint("[%s]" % report.grade, "ok" if report.passed else "error")))
    lines.append("   %s   %s" % (
        _paint("📁", "dim"),
        _paint(report.root, "dim")))
    stats = report.stats
    lines.append("   %s 正文 %d 行 · 脚本 %d · 参考 %d · 资源 %d" % (
        _paint("📄", "dim"), stats.get("body_lines", 0), stats.get("scripts", 0),
        stats.get("references", 0), stats.get("assets", 0)))
    lines.append("   %s %s" % (_paint("💬", "dim"), _paint(stats.get("comments", ""), "dim")))
    lines.append("")

    if not report.findings:
        lines.append("   " + _paint("✨ 未发现任何问题，规范度优秀。", "ok"))
        lines.append("")
        return

    visible = [f for f in report.findings if show_info or f.severity != "info"]
    if max_findings and len(visible) > max_findings:
        visible = visible[:max_findings]

    for finding in visible:
        badge = _paint(SEVERITY_BADGE.get(finding.severity, "[INFO ]"),
                       SEVERITY_COLOR.get(finding.severity, "info"))
        lines.append("   %s %s  %s" % (badge, _paint(finding.rule_id, "dim"),
                                       finding.title))
        lines.append("        %s %s" % (_paint("位置", "dim"), finding.location))
        lines.append("        %s %s" % (_paint("说明", "dim"), finding.message))
        if finding.evidence:
            lines.append("        %s %s" % (_paint("命中", "dim"),
                                            _paint(finding.evidence, "warning")))
        lines.append("        %s %s" % (_paint("修复", "dim"), finding.fix))
        lines.append("")

    hidden = len(report.findings) - len(visible)
    if hidden > 0:
        lines.append("   " + _paint("… 另有 %d 项未显示（使用 --all 查看全部）" % hidden, "dim"))
        lines.append("")


# --------------------------------------------------------------------------
# JSON renderer
# --------------------------------------------------------------------------

def render_json(result, indent=2):
    payload = result.to_dict()
    payload["meta"] = {
        "tool": "SkillAudit",
        "version": _version(),
        "sarif_rules": len(_sarif_rules()),
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent)


def _version():
    try:
        from . import __version__
        return __version__
    except Exception:  # pragma: no cover
        return "0.0.0"


# --------------------------------------------------------------------------
# SARIF renderer (GitHub code scanning friendly)
# --------------------------------------------------------------------------

def _sarif_rules():
    rules = []
    seen = set()
    for pattern in PATTERNS:
        if pattern.rule_id in seen:
            continue
        seen.add(pattern.rule_id)
        rules.append({
            "id": pattern.rule_id,
            "name": pattern.title,
            "shortDescription": {"text": pattern.title},
            "fullDescription": {"text": "%s 修复建议：%s" % (pattern.message, pattern.fix)},
            "help": {"text": pattern.fix},
            "defaultConfiguration": {
                "level": _sarif_level(pattern.severity),
            },
            "properties": {"tags": ["skillaudit", "security", "agent-skills"]},
        })

    extra = [
        ("SA001", "缺少 SKILL.md 清单文件", "技能包根目录未找到 SKILL.md。"),
        ("SA002", "front matter 解析失败", "front matter 无法解析。"),
        ("SA003", "缺少 YAML front matter", "SKILL.md 顶部缺少 YAML front matter。"),
        ("SA010", "front matter 缺少 name", "未提供 name 字段。"),
        ("SA011", "name 命名不规范", "name 不符合小写字母数字连字符规范。"),
        ("SA012", "name 过长", "name 长度超过 64 字符上限。"),
        ("SA013", "name 与目录名不一致", "front matter 的 name 与目录名不一致。"),
        ("SA014", "name 使用保留前缀", "name 使用了可能被保留的前缀。"),
        ("SA020", "front matter 缺少 description", "未提供 description 字段。"),
        ("SA021", "description 过短", "description 长度不足 20 字符。"),
        ("SA022", "description 过长", "description 超过 1024 字符。"),
        ("SA023", "description 缺少触发条件", "description 未见 Use when 类触发描述。"),
        ("SA024", "description 结构错误", "description 必须为字符串。"),
        ("SA030", "存在未知 front matter 字段", "front matter 含未知字段。"),
        ("SA040", "SKILL.md 正文为空", "front matter 之后没有正文。"),
        ("SA041", "SKILL.md 正文过长", "正文超过 500 行上限。"),
        ("SA042", "SKILL.md 正文偏长", "正文超过建议的 300 行。"),
        ("SA043", "正文缺少结构化小节", "标题数量过少。"),
        ("SA044", "代码块围栏未闭合", "``` 围栏数量为奇数。"),
        ("SA045", "缺少可执行示例", "正文缺少命令或代码示例。"),
        ("SA050", "存在冗余文件", "技能包内存在不会被加载的冗余文件。"),
        ("SA051", "技能包文件过多", "附加文件数量过多，建议拆分。"),
        ("SA052", "资源嵌套层级过深", "资源目录嵌套超过 2 层。"),
        ("SA060", "正文引用了不存在的资源", "Markdown 链接目标不存在。"),
        ("SA061", "references 文件未被引用", "references 下文件未在正文引用。"),
        ("SC001", "allowed-tools 字段重复定义", "重复声明 allowed-tools 系列字段。"),
        ("SC002", "allowed-tools 为空格分隔字符串", "使用了传统空格分隔写法。"),
        ("SC003", "allowed-tools 含非法条目", "工具名无法识别。"),
        ("SC004", "使用了 Claude Code 专有字段", "字段仅在 Claude Code 生效。"),
        ("SC005", "未声明 license 字段", "front matter 缺少 license。"),
        ("SC006", "version 字段为空", "version 声明但取值为空。"),
        ("SC010", "脚本缺少 shebang 声明", "脚本首行缺少 #!。"),
        ("SC011", "Shell 脚本缺少可执行权限", "脚本未设置可执行位。"),
        ("SC012", "PowerShell 脚本跨平台受限", ".ps1 在 macOS/Linux 不可用。"),
        ("SC020", "未位于标准安装目录", "不在已知安装根目录下。"),
        ("SC021", "长正文未拆分到 references", "长正文缺少 references 拆分。"),
    ]
    for rule_id, title, desc in extra:
        if rule_id in seen:
            continue
        seen.add(rule_id)
        rules.append({
            "id": rule_id,
            "name": title,
            "shortDescription": {"text": title},
            "fullDescription": {"text": desc},
            "defaultConfiguration": {"level": "warning"},
            "properties": {"tags": ["skillaudit", "specification", "agent-skills"]},
        })
    return rules


def _sarif_level(severity):
    return {"error": "error", "warning": "warning", "info": "note"}.get(severity, "warning")


def render_sarif(result, base_uri="file://"):
    results = []
    for report in result.reports:
        for finding in report.findings:
            path = finding.file or (report.name + "/SKILL.md")
            if finding.file and not os.path.isabs(finding.file):
                uri = base_uri.rstrip("/") + "/" + path.replace(os.sep, "/")
            else:
                uri = path
            results.append({
                "ruleId": finding.rule_id,
                "level": _sarif_level(finding.severity),
                "message": {"text": "%s —— %s 建议：%s" % (
                    finding.title, finding.message, finding.fix)},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": uri.lstrip("/")
                                             if uri.startswith("file://") else uri},
                        "region": {
                            "startLine": finding.line or 1,
                            "startColumn": 1,
                        },
                    }
                }],
            })

    return json.dumps({
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
                   "Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "SkillAudit",
                    "version": _version(),
                    "informationUri": "https://github.com/gitstq/SkillAudit",
                    "rules": _sarif_rules(),
                }
            },
            "results": results,
        }],
    }, ensure_ascii=False, indent=2)
