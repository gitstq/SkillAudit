#!/usr/bin/env python3
"""Minimal CSV profiler used by the csv-insight example skill."""

import argparse
import csv
import json
import sys

SAMPLE_LIMIT = 5000


def infer(value):
    if value in ("", None):
        return None
    try:
        int(value)
        return "int"
    except ValueError:
        pass
    try:
        float(value)
        return "float"
    except ValueError:
        pass
    if value.lower() in ("true", "false"):
        return "bool"
    return "str"


def profile(path, limit, use_full):
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        for index, row in enumerate(reader):
            if not use_full and index >= limit:
                break
            rows.append(row)
    columns = []
    total = max(1, len(rows))
    for field in fields:
        values = [row.get(field, "") for row in rows]
        types = [t for t in (infer(v) for v in values) if t]
        blanks = sum(1 for v in values if v in ("", None))
        columns.append({
            "column": field,
            "inferred_type": max(set(types), key=types.count) if types else "empty",
            "null_rate": round(blanks / float(total), 4),
            "distinct": len(set(values)),
        })
    return {"rows_scanned": len(rows), "columns": columns}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Profile a CSV file")
    parser.add_argument("--file", required=True, help="Path to the CSV file")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--full", action="store_true", help="Scan every row")
    args = parser.parse_args(argv)

    columns = profile(args.file, SAMPLE_LIMIT, args.full)["columns"]
    if args.format == "json":
        print(json.dumps(columns, ensure_ascii=False, indent=2))
    else:
        for item in columns:
            print("%-20s %-12s %8.2f%% %8d" % (
                item["column"], item["inferred_type"],
                item["null_rate"] * 100, item["distinct"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
