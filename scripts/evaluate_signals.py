"""
Open シグナルを price_data に基づいて評価し、status を確定する。

使い方:
  python3 scripts/evaluate_signals.py
  python3 scripts/evaluate_signals.py --max-holding-days 30

GitHub Actions の daily cron から毎晩呼ぶ想定。
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services.signal_tracker import (  # noqa: E402
    evaluate_open_signals,
    DEFAULT_MAX_HOLDING_DAYS,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-holding-days", type=int, default=DEFAULT_MAX_HOLDING_DAYS)
    args = ap.parse_args()

    stats = evaluate_open_signals(max_holding_days=args.max_holding_days)
    print(f"[evaluator] done: {stats}")


if __name__ == "__main__":
    main()
