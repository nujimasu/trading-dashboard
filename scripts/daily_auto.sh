#!/bin/bash
# 毎朝自動実行: 日次調整スクリプト
# macOS LaunchAgent から呼び出される

DASHBOARD_DIR="/Users/junusami/Documents/Claudeプライベート/trading-dashboard"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
LOG="$DASHBOARD_DIR/logs/daily_auto.log"

mkdir -p "$DASHBOARD_DIR/logs"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"
cd "$DASHBOARD_DIR" && "$PYTHON" pipeline/run_pipeline.py --daily-full >> "$LOG" 2>&1
echo "" >> "$LOG"
