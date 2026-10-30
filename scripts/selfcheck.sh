#!/usr/bin/env bash
# Dogfood SkillAudit with SkillAudit itself.
#
# Assertions performed:
#   1. the hostile example must be rejected (exit code 1)
#   2. the clean example must pass with a perfect score (exit code 0)
#   3. the text / json / sarif renderers must all produce valid output
#
# Exits 0 only when every assertion holds.
set -uo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
export PYTHONPATH="src:${PYTHONPATH:-}"

failed=0

pass() { printf '   ✅ %s\n' "$1"; }
fail() { printf '   ❌ %s\n' "$1"; failed=1; }

printf '🛡️  SkillAudit self-check\n\n'

# --- 1. hostile example must fail -----------------------------------------
printf '🔎 examples/bad-skill must be rejected\n'
"$PY" -m skillaudit audit examples/bad-skill --single --no-banner --quiet >/dev/null 2>&1
case $? in
    0) fail "expected a non-zero exit code for the hostile example" ;;
    1) pass "hostile example rejected with exit code 1" ;;
    *) fail "unexpected exit code for the hostile example" ;;
esac

# --- 2. clean example must score 100 --------------------------------------
printf '\n🔎 examples/skills/csv-insight must score 100/100\n'
out=$("$PY" -m skillaudit audit examples/skills/csv-insight --single --no-banner 2>&1)
code=$?
if [ "$code" -eq 0 ]; then
    if printf '%s' "$out" | grep -q "100/100"; then
        pass "clean example passed with 100/100 (exit 0)"
    else
        fail "clean example passed but did not reach 100/100"
    fi
else
    fail "clean example exited $code, expected 0"
fi

# --- 3. json renderer ------------------------------------------------------
printf '\n🔎 json renderer\n'
tmp_json="$(mktemp)"
"$PY" -m skillaudit audit examples -f json -o "$tmp_json" --no-banner >/dev/null 2>&1 || true
if [ -s "$tmp_json" ] && "$PY" -c 'import json,sys; json.load(open(sys.argv[1]))' "$tmp_json" >/dev/null 2>&1; then
    pass "produced valid JSON"
else
    fail "JSON output missing or unparseable"
fi
rm -f "$tmp_json"

# --- 4. sarif renderer -----------------------------------------------------
printf '\n🔎 sarif renderer\n'
tmp_sarif="$(mktemp)"
"$PY" -m skillaudit audit examples -f sarif -o "$tmp_sarif" --no-banner >/dev/null 2>&1 || true
rules=$("$PY" - "$tmp_sarif" <<'PY'
import json, sys
try:
    doc = json.load(open(sys.argv[1]))
    run = doc.get("runs", [{}])[0]
    print(len(run.get("tool", {}).get("driver", {}).get("rules", [])))
except Exception:
    print(0)
PY
)
if [ "$rules" -gt 0 ]; then
    pass "produced SARIF carrying $rules rule descriptors"
else
    fail "SARIF output carried no rule descriptors"
fi
rm -f "$tmp_sarif"

printf '\n'
if [ "$failed" -eq 0 ]; then
    printf '✅ 自检全部通过 · all self-check assertions passed\n'
    exit 0
fi
printf '❌ 自检存在失败项 · self-check failed\n'
exit 1
