---
name: csv-insight
description: >-
  Profile and validate CSV/TSV files — column types, null rates, duplicate keys
  and basic statistics. Use when the user asks to inspect, summarize, clean or
  sanity-check a tabular data file.
version: 1.0.0
license: MIT
metadata:
  author: SkillAudit examples
allowed-tools:
  - Read
  - Grep
  - Bash
---

# csv-insight

对 CSV / TSV 表格做一次"体检"，输出列类型、空值率、重复主键与基础统计量。

## 使用步骤

1. 让脚本分析目标文件：

   ```bash
   python scripts/analyze.py --file data.csv --format table
   ```

2. 若返回非零退出码，说明存在重复主键或全空列，按提示复核数据源。

## 输出说明

| 字段 | 含义 |
| :--- | :--- |
| column | 列名 |
| inferred_type | 推断类型（int / float / bool / date / str） |
| null_rate | 空值占比 |
| distinct | 去重后取值数 |

## 参考资料

- 字段推断与异常判定细则见 [references/rules.md](references/rules.md)

## 注意事项

- 默认只读入前 5000 行做推断，全量统计请加 `--full`。
- 所有操作均为本地只读，不会写入或修改输入文件，也不会发起任何网络请求。
