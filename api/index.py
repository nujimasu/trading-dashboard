"""Vercel Serverless Function entrypoint.

Vercel の Python runtime がこのファイルの ASGI アプリ (`app`) を検出して起動する。
全リクエストは vercel.json の routes によって当ファイルへ集約される。
cron バッチ (pipeline/) は GitHub Actions 側で実行するため、ここには含めない。
"""
import sys
from pathlib import Path

# リポジトリルートを import パスに追加（backend.* / config を解決するため）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app import app  # noqa: E402

__all__ = ["app"]
