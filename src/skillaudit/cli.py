# -*- coding: utf-8 -*-
"""Command line interface for SkillAudit.

Design goals:

* ``skaudit audit`` is safe to drop into CI — non-zero exit status summarises
  severity, machine-readable JSON / SARIF are one flag away.
* Every flag has a sensible default so ``skaudit audit .`` just works.
* ``NO_COLOR`` / non-TTY output automatically degrades to plain text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from . import __version__
from .audit import DEFAULT_ENABLED, audit_path, audit_single, filter_by_rule
from .discovery import discover, detect_platform, is_skill_dir
from .render import render_json, render_sarif, render_text
from .rules_security import PATTERNS
from .scoring import WEIGHTS

PROG = "skaudit"

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_WARNING = 2

_LOGO = """
   ____  _    _           _    _ _ _    _
  / ___|| | _(_)_ __     / \\  | | | |  (_)_ __
  \\___ \\| |/ / | '_ \\   / _ \\ | | | |  | | '_ \\
   ___) |   <| | | | | / ___ \\| | | |__| | |_) |
  |____/|_|\\_\\_|_| |_|/_/   \\_\\_|_|_____/| .__/
                                          |_|
"""


# --------------------------------------------------------------------------
# Argument plumbing
# --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Agent Skills (SKILL.md) 规范校验与安全审计引擎",
        epilog="退出码：0=全部通过 / 1=存在 error / 2=仅有 warning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version",
                        version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="command", metavar="{audit,list,rules}")

    # -- audit -----------------------------------------------------------
    audit = sub.add_parser("audit", help="审计一个技能目录或包含多个技能的项目")
    _audit_args(audit)

    # -- list ------------------------------------------------------------
    listing = sub.add_parser("list", help="列出发现到的技能包")
    listing.add_argument("path", nargs="?", default=".", help="扫描路径（默认当前目录）")
    listing.add_argument("-j", "--json", action="store_true", help="输出 JSON")

    # -- rules -----------------------------------------------------------
    rules_cmd = sub.add_parser("rules", help="列出全部内置规则")
    rules_cmd.add_argument("-j", "--json", action="store_true", help="输出 JSON")
    rules_cmd.add_argument("filter", nargs="?", default=None,
                           help="按规则 ID 前缀过滤，例如 SS1")
    return parser


def _audit_args(parser):
    parser.add_argument("path", nargs="?", default=None, help="扫描路径（默认当前目录）")
    parser.add_argument("--single", action="store_true",
                        help="把 path 视为单个技能目录，不做递归发现")
    parser.add_argument("-f", "--format", choices=("text", "json", "sarif"),
                        default="text", help="输出格式（默认 text）")
    parser.add_argument("-o", "--output", default=None,
                        help="写入文件而不是标准输出")
    parser.add_argument("-s", "--severity", choices=("info", "warning", "error"),
                        default="info", help="最低报告级别（默认 info）")
    parser.add_argument("-c", "--category", action="append", default=None,
                        choices=("spec", "security", "compat"),
                        help="仅运行指定规则组，可重复传入")
    parser.add_argument("--include", default=None,
                        help="仅保留规则 ID 前缀，逗号分隔，例如 SA01,SS12")
    parser.add_argument("--exclude", default=None,
                        help="排除规则 ID 前缀，逗号分隔，例如 SC")
    parser.add_argument("-a", "--all", action="store_true",
                        help="显示全部问题，包含 info 级")
    parser.add_argument("--max-findings", type=int, default=0,
                        help="每个技能包最多显示 N 条问题（0 表示不限）")
    parser.add_argument("--fail-on", choices=("none", "warning", "error"),
                        default="error", help="在什么级别上让退出码非零")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="安静模式，仅输出结论行")
    parser.add_argument("--no-banner", action="store_true", help="不显示标题图形")


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def cmd_audit(args) -> int:
    path = args.path or "."
    target = os.path.abspath(path)
    if not os.path.exists(target):
        _write(args, "错误：路径不存在 —— %s" % target, stream=sys.stderr)
        return EXIT_ERROR

    categories = tuple(args.category) if args.category else None

    if args.single:
        result = audit_single(target, categories=categories,
                              min_severity=args.severity)
    else:
        result = audit_path(target, categories=categories,
                            min_severity=args.severity)

    include = args.include.split(",") if args.include else None
    exclude = args.exclude.split(",") if args.exclude else None
    if include or exclude:
        result = filter_by_rule(result, include, exclude)

    if args.format == "json":
        payload = render_json(result)
    elif args.format == "sarif":
        payload = render_sarif(result)
    else:
        payload = render_text(result, show_info=True,
                              max_findings=args.max_findings or None)
        if args.quiet:
            lines = []
            for report in result.reports:
                lines.append("%-40s %3d  %s" % (report.name, report.score, report.grade))
            payload = "\n".join(lines)
        elif not args.no_banner:
            payload = _LOGO + payload

    _write(args, payload)
    return _decide_exit(result, args.fail_on)


def cmd_list(args) -> int:
    root = os.path.abspath(args.path or ".")
    packages = discover(root)
    if args.json:
        payload = json.dumps([p.to_dict() for p in packages],
                             ensure_ascii=False, indent=2)
    else:
        if not packages:
            payload = "未在 %s 下发现技能包。" % root
        else:
            rows = ["%-40s %-16s %s" % ("技能包", "平台", "路径")]
            rows.append("-" * 96)
            for package in packages:
                rows.append("%-40s %-16s %s" % (
                    package.name[:40], package.platform or "-", package.root))
            payload = "\n".join(rows)
    _write(args, payload)
    return EXIT_OK


def cmd_rules(args) -> int:
    rows = []
    prefix = (args.filter or "").upper()
    for pattern in PATTERNS:
        if prefix and not pattern.rule_id.startswith(prefix):
            continue
        rows.append({
            "rule_id": pattern.rule_id,
            "title": pattern.title,
            "severity": pattern.severity,
            "category": "security",
            "penalty": WEIGHTS.get(pattern.severity, 1),
            "fix": pattern.fix,
        })

    extra = [
        ("SA001", "缺少 SKILL.md 清单文件", "error", "spec", "在根目录新建 SKILL.md。"),
        ("SA002", "front matter 解析失败", "error", "spec", "修正 YAML 缩进与引号。"),
        ("SA003", "缺少 YAML front matter", "error", "spec", "补充 --- 包裹的 front matter。"),
        ("SA010", "front matter 缺少 name", "error", "spec", "添加 name 字段。"),
        ("SA011", "name 命名不规范", "error", "spec", "仅使用小写字母、数字与连字符。"),
        ("SA012", "name 过长", "error", "spec", "缩短到 64 字符以内。"),
        ("SA013", "name 与目录名不一致", "warning", "spec", "让 name 与目录名保持一致。"),
        ("SA014", "name 使用保留前缀", "warning", "spec", "避免使用 claude/anthropic 前缀。"),
        ("SA020", "front matter 缺少 description", "error", "spec", "补充用途与触发条件描述。"),
        ("SA021", "description 过短", "warning", "spec", "至少 20 字符。"),
        ("SA022", "description 过长", "warning", "spec", "控制在 1024 字符内。"),
        ("SA023", "description 缺少触发条件", "info", "spec", "追加 Use when ... 描述。"),
        ("SA024", "description 结构错误", "error", "spec", "改为字符串。"),
        ("SA030", "存在未知 front matter 字段", "info", "spec", "移除或文档化该字段。"),
        ("SA040", "SKILL.md 正文为空", "error", "spec", "补充操作步骤。"),
        ("SA041", "SKILL.md 正文过长", "error", "spec", "拆分到 references/。"),
        ("SA042", "SKILL.md 正文偏长", "warning", "spec", "控制在 300 行内。"),
        ("SA043", "正文缺少结构化小节", "warning", "spec", "用 ## 划分小节。"),
        ("SA044", "代码块围栏未闭合", "warning", "spec", "补齐 ``` 围栏。"),
        ("SA045", "缺少可执行示例", "info", "spec", "补充可执行示例。"),
        ("SA050", "存在冗余文件", "info", "spec", "删除或移入 references/。"),
        ("SA051", "技能包文件过多", "warning", "spec", "拆分为多个技能包。"),
        ("SA052", "资源嵌套层级过深", "info", "spec", "扁平化目录。"),
        ("SA060", "正文引用了不存在的资源", "error", "spec", "补齐文件或修正链接。"),
        ("SA061", "references 文件未被引用", "info", "spec", "在正文中引用。"),
        ("SC001", "allowed-tools 字段重复定义", "warning", "compat", "保留一种写法。"),
        ("SC002", "allowed-tools 为空格分隔字符串", "info", "compat", "改用 YAML 列表。"),
        ("SC003", "allowed-tools 含非法条目", "warning", "compat", "使用标准工具名。"),
        ("SC004", "使用了 Claude Code 专有字段", "info", "compat", "在 README 说明平台要求。"),
        ("SC005", "未声明 license 字段", "info", "compat", "添加 license。"),
        ("SC006", "version 字段为空", "info", "compat", "填入语义化版本号。"),
        ("SC010", "脚本缺少 shebang 声明", "warning", "compat", "首行加入 #!。"),
        ("SC011", "Shell 脚本缺少可执行权限", "info", "compat", "chmod +x。"),
        ("SC012", "PowerShell 脚本跨平台受限", "info", "compat", "提供 .sh/.py 版本。"),
        ("SC020", "未位于标准安装目录", "info", "compat", "放入标准 skills/ 目录。"),
        ("SC021", "长正文未拆分到 references", "warning", "compat", "拆分可选细节。"),
    ]
    for rule_id, title, severity, category, fix in extra:
        if prefix and not rule_id.startswith(prefix):
            continue
        rows.append({
            "rule_id": rule_id,
            "title": title,
            "severity": severity,
            "category": category,
            "penalty": WEIGHTS.get(severity, 1),
            "fix": fix,
        })

    rows.sort(key=lambda r: r["rule_id"])

    if args.json:
        _write(args, json.dumps(rows, ensure_ascii=False, indent=2))
        return EXIT_OK

    lines = ["%-8s %-8s %-10s %-4s %s" % ("规则ID", "类别", "级别", "扣分", "标题"),
             "-" * 88]
    for row in rows:
        lines.append("%-8s %-8s %-10s %-4s %s" % (
            row["rule_id"], row["category"], row["severity"],
            row["penalty"], row["title"]))
    lines.append("")
    lines.append("共 %d 条规则。" % len(rows))
    _write(args, "\n".join(lines))
    return EXIT_OK


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _write(args, payload, stream=None):
    stream = stream or sys.stdout
    output = getattr(args, "output", None)
    if output:
        try:
            with open(output, "w", encoding="utf-8") as handle:
                handle.write(payload)
                if not payload.endswith("\n"):
                    handle.write("\n")
            return
        except OSError as exc:
            print("写入文件失败：%s" % exc, file=sys.stderr)
            sys.exit(EXIT_ERROR)
    print(payload)


def _decide_exit(result, fail_on):
    if fail_on == "none":
        return EXIT_OK
    if not result.reports:
        return EXIT_ERROR
    if fail_on == "warning":
        if result.error_count or result.warning_count:
            return EXIT_ERROR
        return EXIT_OK
    if result.error_count:
        return EXIT_ERROR
    if result.warning_count:
        return EXIT_WARNING
    return EXIT_OK


def main(argv=None):
    """Entry point used by the ``skaudit`` console script."""
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    # Support the shorthand `skaudit .` and bare `skaudit` → audit cwd.
    if argv and not argv[0].startswith("-") and argv[0] not in (
            "audit", "list", "rules"):
        argv = ["audit"] + argv
    elif not argv:
        argv = ["audit", "."]

    args = parser.parse_args(argv)

    handlers = {"audit": cmd_audit, "list": cmd_list, "rules": cmd_rules}
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return EXIT_OK
    try:
        return handler(args)
    except KeyboardInterrupt:  # pragma: no cover
        print("\n已取消。", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
