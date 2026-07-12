import unittest

from backend.services.signal_tracker import _evaluate_resistance_ema20


def bar(day, o, h, l, c):
    return {"ticker": "TEST", "date": day, "open": o, "high": h, "low": l, "close": c}


class StructuralExitTest(unittest.TestCase):
    def base(self):
        bars = []
        for i in range(1, 31):
            bars.append(bar(f"2025-01-{i:02d}", 100, 101, 99, 100))
        sig = {"signal_date": "2025-01-30", "direction": "LONG",
               "entry_price": 100, "stop_price": 90,
               "tp1_price": 110, "target_price": 110}
        meta = {"exit_mode": "resistance_ema20", "exit_fraction": 2 / 3,
                "cost_bps": 0}
        return bars, sig, meta

    def test_stop_before_target(self):
        bars, sig, meta = self.base()
        bars.append(bar("2025-01-31", 100, 101, 89, 90))
        got = _evaluate_resistance_ema20(sig, bars, "2025-01-31", 30, meta)
        self.assertEqual(got["status"], "stopped")
        self.assertAlmostEqual(got["realized_r"], -1.0)

    def test_target_then_break_even(self):
        bars, sig, meta = self.base()
        bars.extend([
            bar("2025-01-31", 100, 111, 99, 110),
            bar("2025-02-01", 105, 107, 100, 101),
        ])
        got = _evaluate_resistance_ema20(sig, bars, "2025-02-01", 30, meta)
        self.assertEqual(got["status"], "tp1_hit_be")
        self.assertAlmostEqual(got["realized_r"], 2 / 3)

    def test_target_then_ema_exit_next_open(self):
        bars, sig, meta = self.base()
        bars.extend([
            bar("2025-01-31", 100, 111, 99, 110),
            bar("2025-02-01", 105, 107, 101, 99),
            bar("2025-02-02", 98, 100, 97, 99),
        ])
        got = _evaluate_resistance_ema20(sig, bars, "2025-02-02", 30, meta)
        self.assertEqual(got["status"], "ema20_exit")
        self.assertAlmostEqual(got["realized_r"], 0.6)

    def test_full_exit_at_resistance_target(self):
        bars, sig, meta = self.base()
        meta.update(exit_mode="resistance_target", exit_fraction=1.0)
        bars.append(bar("2025-01-31", 100, 111, 99, 110))
        got = _evaluate_resistance_ema20(sig, bars, "2025-01-31", 30, meta)
        self.assertEqual(got["status"], "tp2_hit")
        self.assertAlmostEqual(got["realized_r"], 1.0)

    def test_open_rr_gate_skips_trade(self):
        bars, sig, meta = self.base()
        meta.update(exit_mode="resistance_target", exit_fraction=1.0,
                    min_entry_rr=1.5, max_entry_rr=2.0)
        bars.append(bar("2025-01-31", 100, 111, 99, 110))
        got = _evaluate_resistance_ema20(sig, bars, "2025-01-31", 30, meta)
        self.assertEqual(got["status"], "invalid")
        self.assertIsNone(got["realized_r"])

    def test_open_rr_gate_accepts_and_exits_at_17r(self):
        bars, sig, meta = self.base()
        sig["tp1_price"] = sig["target_price"] = 117
        meta.update(exit_mode="resistance_target", exit_fraction=1.0,
                    min_entry_rr=1.5, max_entry_rr=2.0)
        bars.append(bar("2025-01-31", 100, 118, 99, 117))
        got = _evaluate_resistance_ema20(sig, bars, "2025-01-31", 30, meta)
        self.assertEqual(got["status"], "tp2_hit")
        self.assertAlmostEqual(got["realized_r"], 1.7)


if __name__ == "__main__":
    unittest.main()
