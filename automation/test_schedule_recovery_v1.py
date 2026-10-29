"""Safeguards for automated Meta catch-up when GitHub misses scheduled runs."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from automation.schedule_recovery_v1 import SWEEP_CRON, select_due_mode

IST = ZoneInfo("Asia/Kolkata")


def at(h, m):
    return datetime(2026, 10, 29, h, m, tzinfo=IST)


class ScheduleRecoveryTests(unittest.TestCase):
    def test_original_budget_before_ist_slot_never_publishes(self):
        self.assertIsNone(select_due_mode("0 3 * * *", at(3, 20), lambda _: False))
        self.assertIsNone(select_due_mode("0 3 * * *", at(8, 29), lambda _: False))

    def test_original_budget_runs_when_due_and_missing(self):
        self.assertEqual("budget", select_due_mode("0 3 * * *", at(8, 31), lambda _: False))

    def test_main_run_does_not_duplicate_published_mode(self):
        self.assertIsNone(select_due_mode("0 3 * * *", at(11, 40), lambda _: True))

    def test_offminute_sweep_fills_missed_budget(self):
        self.assertEqual("budget", select_due_mode(SWEEP_CRON, at(8, 47), lambda _: False))

    def test_sweep_waits_until_each_format_due(self):
        self.assertEqual("budget", select_due_mode(SWEEP_CRON, at(13, 17), lambda m: m == "brand_budget"))
        self.assertEqual(
            "brand_budget",
            select_due_mode(SWEEP_CRON, at(13, 47), lambda m: m == "budget"),
        )

    def test_comparison_recovers_when_other_two_are_published(self):
        self.assertEqual(
            "comparison",
            select_due_mode(SWEEP_CRON, at(19, 47), lambda m: m != "comparison"),
        )

    def test_ambiguous_budget_does_not_starve_other_modes(self):
        chosen = [select_due_mode(SWEEP_CRON, at(h, 17), lambda _: False) for h in range(19, 22)]
        self.assertEqual({"budget", "brand_budget", "comparison"}, set(chosen))

    def test_all_done_skips_unnecessary_rendering(self):
        self.assertIsNone(select_due_mode(SWEEP_CRON, at(23, 17), lambda _: True))

    def test_bad_cron_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            select_due_mode("invalid", at(10, 0), lambda _: False)

    def test_unaware_clock_rejected(self):
        with self.assertRaises(ValueError):
            select_due_mode(SWEEP_CRON, datetime(2026, 10, 29, 11, 0), lambda _: False)


if __name__ == "__main__":
    unittest.main()
