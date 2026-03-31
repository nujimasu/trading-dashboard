"""
Stage 5: Enrich Stage 4 survivors with FMP fundamental data.
Only runs for tickers that passed RR filter (~10-15 stocks).
Cost: ~3 FMP calls per ticker.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.services.fundamentals import get_or_fetch_fundamentals
from backend.db import db_cursor


def run(tickers: list[str]) -> list[str]:
    print(f"[Stage5] Fetching fundamentals for {len(tickers)} tickers...")
    enriched = []

    for ticker in tickers:
        try:
            data = get_or_fetch_fundamentals(ticker)
            if data:
                enriched.append(ticker)
                sector = data.get("sector", "N/A")
                eps_g  = data.get("eps_growth_yoy")
                surprise = data.get("earnings_surprise_pct")
                print(f"  ✅ {ticker}: sector={sector}, EPS growth={eps_g}%, surprise={surprise}%")
            else:
                enriched.append(ticker)  # keep even without fundamentals
                print(f"  ⚠️  {ticker}: no fundamentals (API unavailable or limit reached)")
        except Exception as e:
            print(f"  [ERR] {ticker}: {e}")
            enriched.append(ticker)

    print(f"[Stage5] Done. {len(enriched)} tickers enriched.")
    return enriched


if __name__ == "__main__":
    from backend.db import init_db
    init_db()
    run(["NVDA", "AAPL", "MSFT"])
