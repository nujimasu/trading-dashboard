"""
Trading Dashboard - Configuration
"""
import os
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH  = DATA_DIR / "trading.db"
DATA_DIR.mkdir(exist_ok=True)

# ─── API Keys ────────────────────────────────────────────────────────────────
FMP_API_KEY  = os.getenv("FMP_API_KEY", "")
FMP_BASE_URL = "https://financialmodelingprep.com/stable"   # v3 legacy廃止済み

FRED_API_KEY    = os.getenv("FRED_API_KEY", "")
FRED_BASE_URL   = "https://api.stlouisfed.org/fred"

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
POLYGON_BASE_URL = "https://api.polygon.io"

# ─── Screening Parameters (market-analyst.md準拠) ─────────────────────────
MIN_RR_TIER2       = 1.5   # Tier 2 最低RR
MIN_RR_TIER1       = 2.0   # Tier 1 最低RR
MIN_MARKET_CAP_M   = 300   # 最小時価総額（百万ドル）
RSI_MIN            = 40    # RSI下限
RSI_MAX            = 70    # RSI上限（過熱排除）
PCT_FROM_HIGH_MAX  = 0.15  # 52週高値からの最大乖離率（15%以内）
VOL_CONTRACTION_RATIO = 1.0  # 出来高収縮判定（直近 < 50日平均）
PRICE_RANGE_TIGHTEN_DAYS = 10  # レンジ縮小判定の日数

STOP_WINDOW  = 20   # ストップ計算窓（過去N日最安値）
ATR_PERIOD   = 14
ATR_MULT     = 2.0  # 最大リスク幅（ATR倍率）
TARGET_WINDOW = 100  # 目標値計算窓（過去N日最高値）

# ─── Universe ────────────────────────────────────────────────────────────────
# yfinanceバルクダウンロードのバッチサイズ
DOWNLOAD_BATCH_SIZE = 100
# 1年分のOHLCV
PRICE_HISTORY_PERIOD = "1y"

# FMP APIコール上限（保守的に設定）
FMP_DAILY_LIMIT = 200  # 250が上限だが余裕を持たせる

# ─── Theme Map（テーマ→銘柄リスト） ──────────────────────────────────────
THEME_MAP: dict[str, list[str]] = {
    "AI・機械学習": [
        "NVDA", "MSFT", "GOOGL", "GOOG", "META", "AMD", "AVGO", "ORCL",
        "CRM", "NOW", "SNOW", "PLTR", "AI", "SOUN", "BBAI",
    ],
    "半導体": [
        "NVDA", "AMD", "AVGO", "QCOM", "TSM", "AMAT", "LRCX", "KLAC",
        "MRVL", "ON", "TXN", "INTC", "MU", "SMCI",
    ],
    "クラウド・SaaS": [
        "MSFT", "AMZN", "GOOGL", "CRM", "NOW", "SNOW", "DDOG", "ZS",
        "CRWD", "PANW", "NET", "MDB", "GTLB",
    ],
    "核融合・原子力": [
        "CCJ", "VST", "CEG", "SMR", "NNE", "OKLO", "BWXT", "LEU",
    ],
    "エネルギー転換": [
        "XOM", "CVX", "COP", "PSX", "VLO", "MPC", "SLB", "HAL",
        "FSLR", "ENPH", "NEE", "BEP",
    ],
    "バイオ・ヘルスケア": [
        "LLY", "NVO", "ABBV", "MRK", "PFE", "AMGN", "GILD", "REGN",
        "VRTX", "DXCM", "ISRG", "INTU",
    ],
    "金融・フィンテック": [
        "JPM", "BAC", "GS", "MS", "V", "MA", "AXP", "PYPL", "SQ",
        "COIN", "HOOD",
    ],
    "防衛・宇宙": [
        "LMT", "RTX", "NOC", "GD", "BA", "SPCE", "RKLB", "PL",
    ],
    "消費者・小売": [
        "AMZN", "COST", "WMT", "TGT", "HD", "LOW", "TJX", "LULU",
        "NKE", "DECK",
    ],
}

# ─── Sector Map（GICS大分類→日本語表示名） ───────────────────────────────
# FMP形式 + yfinance形式の両方に対応
SECTOR_DISPLAY: dict[str, str] = {
    # FMP / GICS 標準表記
    "Technology":             "テクノロジー",
    "Health Care":            "ヘルスケア",
    "Financials":             "金融",
    "Consumer Discretionary": "一般消費財",
    "Communication Services": "通信・メディア",
    "Industrials":            "資本財",
    "Consumer Staples":       "生活必需品",
    "Energy":                 "エネルギー",
    "Real Estate":            "不動産",
    "Materials":              "素材",
    "Utilities":              "公益",
    # yfinance 固有の表記（FMPと異なる場合）
    "Healthcare":             "ヘルスケア",
    "Financial Services":     "金融",
    "Consumer Cyclical":      "一般消費財",
    "Consumer Defensive":     "生活必需品",
    "Basic Materials":        "素材",
    "Communication Services": "通信・メディア",
    "Industrials":            "資本財",
}

# ─── Market Health Thresholds ─────────────────────────────────────────────
HEALTH_BULLISH_THRESHOLD = 50   # アップトレンド率50%以上 → Bullish
HEALTH_BEARISH_THRESHOLD = 30   # アップトレンド率30%未満 → Bearish
