#!/bin/bash
# launchd から呼び出されるラッパースクリプト
# venv をアクティベートしてから run_all.py を実行する

set -euo pipefail

PROJECT_DIR="/Users/shroperu/Documents/workspace/trader_position_analytics"
cd "$PROJECT_DIR"

source .venv/bin/activate
exec python3 scripts/run_all.py
