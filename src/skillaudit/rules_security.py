# -*- coding: utf-8 -*-
"""Security rules — static audit of script bodies and manifest prose.

SkillAudit treats every skill package as **untrusted third-party code** that
will eventually be executed by an autonomous agent with the user's privileges.
The rules below are intentionally conservative: they flag *capabilities* that
are commonly abused, using line-oriented pattern matching, and leave the final
judgement to the human reviewer. Nothing here executes or imports the audited
code — analysis is purely textual.
"""

from __future__ import annotations

import os
import re
from typing import List

from .model import Finding

RULESET = "security"

SHELL_SUFFIXES = (".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd")
PYTHON_SUFFIXES = (".py",)
JS_SUFFIXES = (".js", ".mjs", ".cjs", ".ts")

COMMENT_PREFIX = {
    ".py": "#",
    ".sh": "#", ".bash": "#", ".zsh": "#",
    ".rb": "#", ".pl": "#", ".php": "//",
    ".js": "//", ".mjs": "//", ".cjs": "//", ".ts": "//",
    ".ps1": "#",
}


class Pattern(object):
    """A single detection pattern attached to a rule."""

    __slots__ = ("rule_id", "title", "severity", "regex", "message", "fix",
                 "targets", "whole_word")

    def __init__(self, rule_id, title, severity, regex, message, fix,
                 targets=None, whole_word=False):
        self.rule_id = rule_id
        self.title = title
        self.severity = severity
        self.regex = re.compile(regex, re.IGNORECASE)
        self.message = message
        self.fix = fix
        self.targets = tuple(targets) if targets else None
        self.whole_word = whole_word

    def applies_to(self, suffix):
        if not self.targets:
            return True
        return suffix.lower() in self.targets


# --------------------------------------------------------------------------
# Pattern catalogue
# --------------------------------------------------------------------------
# Every entry answers three questions for a reviewer:
#   * what capability was detected,
#   * why an attacker cares about it,
#   * what a legitimate skill should do instead.

PATTERNS = [
    # -- destructive filesystem operations --------------------------------
    Pattern(
        "SS100", "递归强制删除根目录或用户目录", "error",
        r"rm\s+(?:-{1,2}[a-z]*\s+)*(?:/|~|\$HOME|\.\./)+",
        "检测到对根目录、家目录或上级目录的递归删除，一旦执行不可逆。",
        "限定到技能自身的临时目录，删除前先校验路径，并做二次确认。",
        targets=SHELL_SUFFIXES),

    Pattern(
        "SS101", "rm 使用了 -rf 等强制递归参数", "warning",
        r"\brm\s+(-{1,2}[a-zA-Z]*[rf]{2}[a-zA-Z]*|\s+-r[a-zA-Z]*f[a-zA-Z]*)",
        "强制递归删除且无确认步骤，误伤范围难以控制。",
        "改为删除明确路径，并为 destructive 操作增加 dry-run 开关。",
        targets=SHELL_SUFFIXES),

    Pattern(
        "SS102", "格式化磁盘 / 覆写块设备", "error",
        r"\b(mkfs|dd\s+if=.+of=/dev/|shred\s+-|wipefs)\b",
        "直接操作块设备，可能造成整盘数据不可恢复。",
        "移除该操作；这类能力不应出现在可分发技能中。"),

    Pattern(
        "SS103", "危险的文件权限变更", "warning",
        r"\bchmod\s+(?:-{1,2}\S+\s+)?(?:\+[rwxXst]{2,}|[0-7]*777|o\+w|a\+rwx)\b",
        "开放全局可写/可执行权限，易被同主机其他进程篡改。",
        "使用最小权限，例如 700 或 600。",
        targets=SHELL_SUFFIXES),

    Pattern(
        "SS104", "Python 递归删除路径", "warning",
        r"\bshutil\.rmtree\s*\(",
        "脚本会递归删除目录树，路径若来自输入则存在被操纵风险。",
        "硬编码受控目录，删除前校验路径前缀。",
        targets=PYTHON_SUFFIXES),

    # -- remote code execution -------------------------------------------
    Pattern(
        "SS110", "下载即执行（curl/wget 管道到解释器）", "error",
        r"(?:curl|wget)[^\n|;]*\|\s*(?:ba|z|d)?sh\b",
        "远程脚本直接送入 shell 执行，中间人可任意替换载荷。",
        "先下载到临时文件，校验校验和后再执行；优先使用固定版本包。"),

    Pattern(
        "SS111", "危险的 PowerShell 执行模式", "error",
        r"\b(?:iex|Invoke-Expression)\b|\bInvoke-WebRequest\b[^\n]*\|\s*(?:iex|Invoke-Expression)",
        "动态执行字符串或远程下载后直接执行，是典型的落地攻击链。",
        "显式调用已安装的模块，避免拼接字符串后执行。",
        targets=(".ps1", ".bat", ".cmd")),

    Pattern(
        "SS112", "动态代码求值", "error",
        r"\b(eval|exec)\s*\(|\bnew\s+Function\s*\(|\bInvoke-Expression\b"
        r"|\bos\.system\s*\(",
        "动态求值会执行运行时拼接的代码，无法静态审计其意图。",
        "改写为显式调用；确需动态执行时改为白名单分派。"),

    Pattern(
        "SS113", "反序列化不可信数据", "warning",
        r"\b(pickle\.loads?|yaml\.load\s*\((?![^)]*Safe)|marshal\.loads?|eval\(input)",
        "反序列化可执行任意代码，等同于远程代码执行。",
        "使用 yaml.safe_load 或 json 等纯数据格式。",
        targets=PYTHON_SUFFIXES),

    # -- credential / secret access --------------------------------------
    Pattern(
        "SS120", "读取敏感凭据文件", "error",
        r"(?:\.ssh/(?:id_rsa|id_ed25519|id_ecdsa)|\.aws/credentials|\.npmrc|"
        r"\.netrc|\.docker/config\.json|\.kube/config|\.git-credentials|"
        r"CredentialManager|keychain|\.gnupg/)",
        "尝试访问 SSH 私钥或云厂商凭据，属于典型的凭据窃取行为。",
        "若必须读取，请显式要求用户提供自身路径，并在文档中声明用途。"),

    Pattern(
        "SS121", "读取环境变量中的密钥", "warning",
        r"\benviron(?:\.get\(|\b\[)\s*['\"][A-Z_]*(?:KEY|TOKEN|SECRET|PASSWORD|"
        r"PASSWD|CREDENTIAL|API_KEY)['\"]",
        "脚本会读取可能包含密钥的环境变量。",
        "仅在确实需要时读取，且绝不打印或回传其取值。",
        targets=PYTHON_SUFFIXES + JS_SUFFIXES),

    Pattern(
        "SS122", "疑似硬编码密钥或令牌", "error",
        r"\b(?:ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|"
        r"AIza[0-9A-Za-z\-_]{20,})",
        "代码中包含形似高权限令牌的字面量，需立即轮换。",
        "将密钥移出代码，改为运行时从环境变量读取。"),

    Pattern(
        "SS123", "疑似 PEM 私钥块", "error",
        r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+|DSA\s+)?PRIVATE\s+KEY-----",
        "技能包内嵌了 PEM 私钥内容。",
        "删除私钥，改为由使用者自行提供凭据。"),

    Pattern(
        "SS124", "读取 .env 或其它环境文件", "warning",
        r"(?:open|read|cat|Get-Content)\s*\(?['\"]?[^\n]{0,60}\.env\b",
        "读取 .env 可能连带暴露其中的全部密钥。",
        "只读取明确需要的单个变量，避免整文件读入。"),

    # -- network egress ---------------------------------------------------
    Pattern(
        "SS130", "向外部地址发起网络请求", "warning",
        r"\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|"
        r"requests\.(?:get|post|put|patch)|urllib\.request\.urlopen|"
        r"fetch\s*\(|axios\.(?:get|post))\b",
        "脚本存在出网行为，可能把本地上下文发送到第三方服务器。",
        "在文档中声明目标域名与用途；改为默认离线、按需联网。"),

    Pattern(
        "SS131", "疑似 POST 上传本地数据", "error",
        r"\b(?:requests\.post|axios\.post|Invoke-RestMethod\s+-Method\s+Post|"
        r"curl\s+[^\n]*-d\s+@|fetch\s*\([^)]*method\s*:\s*['\"]POST)",
        "向远端提交数据，存在本地文件外泄风险。",
        "明确告知用户上传内容与接收方，并提供 opt-in 开关。"),

    Pattern(
        "SS132", "请求了原始 IP 地址而非域名", "warning",
        r"https?://\d{1,3}(?:\.\d{1,3}){3}",
        "直接访问 IP 通常是为绕过域名审计或 DNS 监控。",
        "改用可审查的域名，并说明服务归属。"),

    # -- persistence / sabotage ------------------------------------------
    Pattern(
        "SS140", "写入 shell 启动脚本实现持久化", "error",
        r"(?:\.bashrc|\.zshrc|\.profile|\.bash_profile|PowerShell[/\\]Profile)",
        "修改 shell 启动脚本会在每次开终端时执行一次，属于持久化驻留。",
        "移除该写入逻辑；如需配置写入，请放到独立配置文件。"),

    Pattern(
        "SS141", "疑似计划任务 / 常驻后门", "error",
        r"\b(crontab|launchctl|systemctl\s+enable|schtasks|nohup\s+.*&\s*$|"
        r"Set-ItemProperty[^\n]*Run)\b",
        "创建定时任务或常驻进程，可能在用户不知情下长期运行。",
        "删除持久化逻辑，保持技能为一次性执行。"),

    Pattern(
        "SS142", "提权执行", "error",
        r"\bsudo\s+(?!-n\b)",
        "请求 root 权限执行，破坏范围远超技能所需。",
        "以普通权限运行；确需提权时向用户明确说明并请求确认。",
        targets=SHELL_SUFFIXES + (".ps1",)),

    Pattern(
        "SS143", "禁用安全机制", "error",
        r"\b(setenforce\s+0|systemctl\s+stop\s+(?:firewalld|ufw|iptables)|"
        r"Set-MpPreference\s+-DisableRealtimeMonitoring|"
        r"ufw\s+disable|iptables\s+-F)\b",
        "关闭防火墙或安全模块，明显超出正常技能职责。",
        "移除该逻辑。"),

    # -- prompt-injection surface (manifest prose) ------------------------
    Pattern(
        "SS150", "正文疑似包含提示注入语句", "error",
        r"(?:ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions|"
        r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions|"
        r"system\s*prompt\s*(?:override|reset)|developer\s+message|"
        r"忽略(?:(?:以上|上面|前面|之前|下述|所有|一切|全部)\s*){0,3}"
        r"(?:的)?\s*(?:指令|指示|提示|规则|要求|约束| Prompt |系统提示)|"
        r"请忽略(?:你的|之前的)?(?:系统|内部)?(?:指令|提示词|设定))",
        "技能正文试图让 Agent 忽略既有指令，属于提示注入高危特征。",
        "删除该语句；技能只能描述任务，不应试图改写系统指令。"),

    Pattern(
        "SS151", "正文疑似诱导静默执行", "warning",
        r"(?:do\s+not\s+(?:tell|inform|ask|mention|report)\s+(?:the\s+)?(?:user| anyone )|"
        r"不要(?:告诉|询问|通知|透露)用户|"
        r"run\s+(?:this\s+)?(?:silently|without\s+asking)|"
        r"never\s+ask\s+for\s+confirmation)",
        "技能指示 Agent 绕过用户确认或隐瞒操作，可能规避人工监督。",
        "移除压制确认的表述，保留用户对敏感操作的知情权。"),

    Pattern(
        "SS152", "正文疑似试图扩大权限范围", "warning",
        r"(?:grant|request|escalate|escalation)\s+(?:admin|root|full|elevated)\s+"
        r"(?:access|permission|privilege)|"
        r"bypass\s+(?:permission|authorization|approval|sandbox)",
        "技能要求提升权限或绕过审批流程。",
        "说明所需的最小权限，由用户决定是否授予。"),

    Pattern(
        "SS153", "正文要求回传敏感信息", "error",
        r"(?:upload|send|post|transmit|forward)\s+(?:the\s+)?"
        r"(?:\.env|credentials|token|password|private\s+key|secret)",
        "技能指示 Agent 上传机密材料到外部。",
        "删除该步骤；敏感数据不应离开本地。"),

    # -- resource exhaustion ---------------------------------------------
    Pattern(
        "SS160", "疑似 fork 炸弹或无限往复", "error",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;|"
        r"\bwhile\s+true\s*;?\s*do\b|\bwhile\s*\(\s*True\s*\)\s*:",
        "存在无限自复制或不设出口的循环，可能耗尽系统资源。",
        "加入退出条件与重试上限。"),

    Pattern(
        "SS161", "缺少超时的网络或子进程调用", "info",
        r"\b(requests\.(?:get|post)|subprocess\.(?:run|Popen|call)|urlopen)\s*"
        r"\((?![^)]*timeout)",
        "网络或子进程调用未设置超时，可能长期挂起。",
        "显式传入 timeout 参数。",
        targets=PYTHON_SUFFIXES),
]


#: Map a fenced code-block info string onto a script suffix.
_FENCE_LANGUAGE = {
    "bash": ".sh", "sh": ".sh", "shell": ".sh", "console": ".sh", "zsh": ".sh",
    "python": ".py", "py": ".py", "python3": ".py",
    "javascript": ".js", "js": ".js", "node": ".js", "typescript": ".js",
    "powershell": ".ps1", "ps1": ".ps1", "ps": ".ps1",
    "ruby": ".rb", "perl": ".pl", "php": ".php",
}

#: Unknown fences are treated conservatively as shell, because "run this" blocks
#: in skill documentation are overwhelmingly shell snippets.
_FENCE_FALLBACK = ".sh"


def check(package):
    """Run every security rule over scripts, prose and fenced code blocks."""
    findings = []

    for rel_path, content in sorted(getattr(package, "script_contents", {}).items()):
        if not content.strip():
            continue
        findings.extend(_scan_text(content, rel_path, "." + _suffix(rel_path)))

    manifest_body = getattr(package, "manifest_body", "") or ""
    manifest_rel = _rel_manifest(package)
    if manifest_body.strip():
        # Prose is checked for prompt-injection / social-engineering wording.
        findings.extend(_scan_text(manifest_body, manifest_rel, ".md",
                                   injection_only=True))
        # Commands embedded in ``` fences are real executable payloads once an
        # agent follows the instructions, so they get the full script treatment.
        for suffix, code, offset in _iter_code_blocks(manifest_body):
            findings.extend(_scan_text(code, manifest_rel, suffix,
                                       line_offset=offset))

    return findings


def _iter_code_blocks(text):
    """Yield ``(suffix, code, first_line_number)`` for each fenced block."""
    blocks = []
    current = []
    start = 0
    suffix = _FENCE_FALLBACK
    inside = False

    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            if not inside:
                info = stripped.lstrip("`").strip().lower()
                suffix = _FENCE_LANGUAGE.get(info.split(",")[0].strip(),
                                             _FENCE_FALLBACK)
                inside = True
                current = []
                start = lineno
            else:
                if current:
                    blocks.append((suffix, "\n".join(current), start + 1))
                inside = False
            continue
        if inside:
            current.append(raw)

    if inside and current:  # unterminated fence — still worth scanning
        blocks.append((suffix, "\n".join(current), start + 1))
    return blocks


def _suffix(path):
    _, ext = os.path.splitext(path)
    return ext.lstrip(".")


def _rel_manifest(package):
    if not package.manifest_path:
        return "SKILL.md"
    try:
        return os.path.relpath(package.manifest_path, package.root).replace(os.sep, "/")
    except ValueError:  # pragma: no cover
        return "SKILL.md"


def _is_comment(line, suffix):
    prefix = COMMENT_PREFIX.get(suffix)
    if not prefix:
        return False
    return line.lstrip().startswith(prefix)


def _scan_text(content, rel_path, suffix, injection_only=False, line_offset=0):
    """Scan text line by line, reporting every pattern that fires.

    Reporting *all* matches rather than only the first one matters for a
    security tool: a line such as ``curl -X POST -d @secret http://x`` can trip
    three distinct capabilities at once, and hiding two of them would leave a
    reviewer with a false sense of completeness.
    """
    out = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_comment(stripped, suffix):
            # Commented-out dangerous commands are dead code, not a capability.
            continue
        seen = set()
        for pattern in PATTERNS:
            if injection_only:
                if not pattern.rule_id.startswith("SS15"):
                    continue
            else:
                if pattern.rule_id.startswith("SS15"):
                    continue  # injection rules only apply to .md prose
                if not pattern.applies_to(suffix):
                    continue
            match = pattern.regex.search(line)
            if not match:
                continue
            if pattern.rule_id in seen:
                continue
            seen.add(pattern.rule_id)
            evidence = match.group(0).strip()
            if len(evidence) > 80:
                evidence = evidence[:77] + "..."
            out.append(Finding(
                pattern.rule_id, pattern.title, severity=pattern.severity,
                category=RULESET, file=rel_path, line=lineno + line_offset,
                message=pattern.message, fix=pattern.fix, evidence=evidence))
    return out
