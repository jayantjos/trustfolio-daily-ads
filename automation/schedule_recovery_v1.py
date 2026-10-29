"""Select a safely due Meta post for a scheduled or delayed GitHub Actions run.

The extra off-minute sweep covers cron delivery delays, but every publication
still uses the existing per-day, per-mode GitHub ledger and live product QA.
No platform IDs, credentials or Meta write operations live in this module.
"""
from datetime import datetime, time
from typing import Callable, Optional

SWEEP_CRON = "17,47 3-17 * * *"
CRON_MODES = {
    "0 3 * * *": "budget",
    "0 5 * * *": "budget",
    "0 8 * * *": "brand_budget",
    "30 10 * * *": "brand_budget",
    "30 13 * * *": "comparison",
    "30 15 * * *": "comparison",
    "0 14 * * *": "budget",
    "0 15 * * *": "brand_budget",
    "45 16 * * *": "comparison",
    "0 16 * * *": "budget",
    "30 16 * * *": "brand_budget",
    "30 17 * * *": "comparison",
}
DUE_IST = (
    ("budget", time(8, 30)),
    ("brand_budget", time(13, 30)),
    ("comparison", time(19, 0)),
)


def select_due_mode(
    cron: str, now_ist: datetime, both_networks_published: Callable[[str], bool]
) -> Optional[str]:
    """Return one missing, due mode; None if it is too early or already complete.

    The sweep rotates the initial candidate across all due formats, so an
    ambiguous/reserved Budget attempt cannot starve Brand or Comparison.
    A 'published' status must be obtained from the immutable per-network
    GitHub ledger, never inferred from workflow success.
    """
    if now_ist.tzinfo is None or now_ist.utcoffset() is None:
        raise ValueError("IST clock must be timezone-aware")
    local_clock = now_ist.timetz().replace(tzinfo=None)
    due = [mode for mode, start in DUE_IST if local_clock >= start]
    if cron == SWEEP_CRON:
        if not due:
            return None
        # Rotate per half-hour without adding any extra published posts.
        index = (now_ist.hour * 2 + (1 if now_ist.minute >= 30 else 0)) % len(due)
        ordered = due[index:] + due[:index]
        for mode in ordered:
            if not both_networks_published(mode):
                return mode
        return None

    mode = CRON_MODES.get(cron)
    if mode is None:
        raise ValueError("Unknown Meta campaign cron expression")
    if mode not in due:
        # Never publish a prior day's delayed cron before its real IST slot.
        return None
    return None if both_networks_published(mode) else mode
