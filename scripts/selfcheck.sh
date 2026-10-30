#!/usr/bin/env bash
# Dogfood SkillAudit: audit the bundled examples with SkillAudit itself.
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHONPATH="src:${PYTHONPATH:-}" python -m skillaudit audit examples
