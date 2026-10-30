#!/usr/bin/env bash
# Run the full SkillAudit test suite without installing anything.
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHONPATH="src:${PYTHONPATH:-}" python -m unittest discover -s tests -v
