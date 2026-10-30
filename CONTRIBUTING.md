# 🤝 Contributing to SkillAudit · 贡献指南

感谢你愿意让 SkillAudit 变得更好！🎉  
Thanks for taking the time to improve SkillAudit! 🎉

本项目同时接受中文与英文反馈，**两种方式任选其一即可**。
This project welcomes both Chinese and English contributions — pick whichever you write faster.

---

## 🌱 快速上手 / Get started

```bash
git clone https://github.com/gitstq/SkillAudit.git
cd SkillAudit

# 跑全量测试 / run the full suite
./scripts/test.sh

# 自检：示例技能包 + 三种输出格式 / self-check: examples + all output formats
./scripts/selfcheck.sh
```

**环境要求 / Requirements**：Python 3.8+，**无需安装任何第三方依赖** / no third-party packages needed.

---

## 🔀 Pull Request 流程 / PR workflow

1. **Fork** 本仓库并克隆到本地 / Fork and clone
2. 新建分支 `feat/<topic>`、`fix/<topic>` / Create a branch
3. 编码 + **补测试** / Code **with tests**
4. 本地全绿后再发起 PR / Open the PR once green locally
5. 在 PR 描述里写清「改了什么 / 为什么 / 如何验证」

### ✍️ 提交信息规范 / Commit message convention

必须遵循 **Angular 规范** / We follow the **Angular convention**：

```text
feat(discovery): 新增 Windsurf skills 根目录识别
fix(yamlmini): 修复折叠块标量吞掉后续字段的问题
docs(readme): 补充 SARIF 集成示例
refactor(scoring): 抽出等级计算函数
test(rules): 补充 SS150 提示注入正反面用例
chore(ci): 添加 GitHub Actions 工作流
```

| 前缀 / Prefix | 用途 / When to use |
| :--- | :--- |
| `feat` | 新增功能 / new feature |
| `fix` | 修复缺陷 / bug fix |
| `docs` | 文档更新 / documentation only |
| `refactor` | 重构（不改动外部行为）/ restructuring without behaviour change |
| `test` | 测试相关 / tests only |
| `chore` | 构建、CI、杂务 / build, CI, housekeeping |

---

## 🧪 贡献规则的硬性要求 / Rules for new rules

新增或修改一条审计规则时，**必须同时提供三件套** / Any new rule **must ship all three**：

1. **规则实现** — 放在 `src/skillaudit/rules_security.py` / `rules_spec.py` / `compat.py`
2. **正面用例** — 一个**不应该触发**该规则的技能包片段
3. **反面用例** — 一个**必须触发**该规则的技能包片段

反面用例里如果包含真实的危险命令（如 `rm -rf /`、`curl | bash`），请**仅保留最小片段**并在注释中标注「仅用于测试 SkillAudit 自身，不代表推荐用法」。
Keep hostile fixtures minimal and comment them as test-only fixtures.

同时请保证 / Also ensure:

- `./scripts/test.sh` 全绿（当前 110 条用例）/ the suite stays green
- 新的 finding 必须携带 `rule_id` + `file` + `line` + `message` + `fix`
- 不得引入任何第三方依赖 / **no new third-party dependencies**

---

## 🐞 Issue 反馈规范 / Reporting issues

提交 Issue 时请附 / Please include:

1. 复现命令与版本（`skaudit --version`）/ exact command and version
2. 最小可复现的 `SKILL.md` 片段（请脱敏）/ minimal snippet (redacted)
3. **期望行为 vs 实际行为** / expected vs actual behaviour

### 🎯 误报 vs 漏报 / False positives vs false negatives

| 类型 | 说明 | 处理方式 |
| :--- | :--- | :--- |
| 误报 / False positive | 正常写法被判违规 | 我们会把该写法加入回归测试白名单 |
| 漏报 / False negative | 明显的危险写法没被抓到 | 我们会补一条新规则 |

这两类反馈**最有价值**，比 Star 更受欢迎 😄

---

## 🧭 代码风格 / Code style

- 遵循 PEP 8，行宽不超过 100 / PEP 8, max line length 100
- 公开函数写 docstring，非显而易见的设计写「为什么」注释
- 保持零第三方依赖：标准库够用就不要加包
- 核心逻辑保持**确定性**：不要引入随机、时间、网络、模型推理

---

## 📄 行为准则 / Code of conduct

保持友善、就事论事。技术分歧欢迎争论，人身攻击不接受。
Be kind and stay technical. Disagree freely, attack arguments rather than people.

---

## 📜 许可声明 / Licensing

你提交的代码默认以本项目相同的 **MIT License** 授权发布。
By contributing you agree your work is licensed under the project's **MIT License**.
