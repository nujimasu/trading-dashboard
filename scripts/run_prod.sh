#!/usr/bin/env bash
# 本番Supabaseに対してパイプライン等を安全に実行するラッパー。
#
# 目的: 秘密(DATABASE_URL/各APIキー)を ps の引数に出さない。
#   `env DATABASE_URL=... python` 形式は argv に値が出て露出するため使わない。
#   ここでは .env を `set -a; source` で環境変数として読み込み、子プロセスへ継承させる。
#
# 使い方:
#   scripts/run_prod.sh [--session] -- <command...>
#     --session : DATABASE_URL の :6543(transaction pooler) を :5432(session pooler) に切替
#                 （長時間・単一接続バッチ向け。短命接続多発なら付けない＝6543のまま）
#
# 例:
#   caffeinate -i scripts/run_prod.sh -- python3 -u pipeline/logic1_scan.py
#   scripts/run_prod.sh --session -- python3 pipeline/run_pipeline.py --skip-download
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "[run_prod] .env が見つかりません" >&2; exit 1; }

# .env を環境へ読み込む（値は argv に出さない）
set -a
# shellcheck disable=SC1091
. ./.env
set +a

USE_SESSION=0
if [ "${1:-}" = "--session" ]; then USE_SESSION=1; shift; fi
[ "${1:-}" = "--" ] && shift

if [ "${USE_SESSION}" = "1" ] && [ -n "${DATABASE_URL:-}" ]; then
  export DATABASE_URL="${DATABASE_URL/:6543/:5432}"
fi

[ "$#" -ge 1 ] || { echo "[run_prod] 実行コマンドを指定してください（-- の後）" >&2; exit 1; }
exec "$@"
