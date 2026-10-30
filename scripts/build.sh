#!/usr/bin/env bash
# Build distributable artifacts (sdist + wheel) for SkillAudit.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> cleaning previous artifacts"
rm -rf build dist ./*.egg-info

echo "==> building sdist + wheel"
python -m build

echo "==> contents"
ls -lh dist/
