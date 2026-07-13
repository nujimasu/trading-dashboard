"""Audit production logic5 SL/TP/RR against point-in-time price history."""

from backend.db import get_connection
from pipeline.logic4_scan import _atr


def main() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT verdict, COUNT(*) AS n, MIN(risk_reward) AS lo,
               MAX(risk_reward) AS hi,
               SUM(CASE WHEN risk_reward BETWEEN 1.5 AND 2.0 THEN 1 ELSE 0 END) AS in_range
        FROM logic5_picks GROUP BY verdict ORDER BY verdict
    """)
    print("VERDICTS")
    for row in cur.fetchall():
        print(dict(row))

    cur.execute("""
        SELECT ticker, scan_date, entry_price, stop_price, tp1_price,
               target_price, risk_reward, verdict
        FROM logic5_picks ORDER BY ticker
    """)
    picks = [dict(row) for row in cur.fetchall()]
    errors = []
    samples = []
    for pick in picks:
        cur.execute("""
            SELECT high, low, close FROM price_data
            WHERE ticker = ? ORDER BY date ASC
        """, (pick["ticker"],))
        bars = [dict(row) for row in cur.fetchall()]
        highs = [float(row["high"]) for row in bars]
        lows = [float(row["low"]) for row in bars]
        closes = [float(row["close"]) for row in bars]
        atr = _atr(highs, lows, closes)[-1] or 0.0
        expected_stop = round(min(lows[-20:]) - 0.1 * atr, 2)
        expected_target = round(max(highs[-61:-1]) * 0.995, 2)
        risk = closes[-1] - expected_stop
        expected_rr = round((expected_target - closes[-1]) / risk, 2) if risk > 0 else None
        stored = (
            float(pick["stop_price"]), float(pick["tp1_price"]),
            float(pick["target_price"]), float(pick["risk_reward"]),
        )
        expected = (expected_stop, expected_target, expected_target, expected_rr)
        ok = all(abs(actual - wanted) < 0.011 for actual, wanted in zip(stored, expected))
        if not ok:
            errors.append((pick["ticker"], stored, expected))
        if len(samples) < 8:
            samples.append((pick["ticker"], stored, expected, pick["verdict"]))

    conn.close()
    print("AUDIT", {"total": len(picks), "errors": len(errors)})
    print("ERRORS", errors[:10])
    print("SAMPLES")
    for sample in samples:
        print(sample)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
