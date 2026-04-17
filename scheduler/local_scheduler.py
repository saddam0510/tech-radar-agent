"""Local scheduler — uses APScheduler to run the pipeline weekly."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.logger import get_logger

logger = get_logger("scheduler")

_WEEKDAY_MAP = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def run_pipeline() -> None:
    """Import and run the full pipeline (deferred import keeps scheduler lightweight)."""
    from main import run  # noqa: PLC0415

    run()


def start(weekday: str = "monday", time: str = "08:00") -> None:
    """Start the blocking scheduler.

    Args:
        weekday: Day of week to run (e.g. "monday").
        time:    Time in "HH:MM" format (local time).
    """
    day_abbr = _WEEKDAY_MAP.get(weekday.lower(), "mon")
    hour, minute = map(int, time.split(":"))

    scheduler = BlockingScheduler(timezone="local")
    trigger = CronTrigger(day_of_week=day_abbr, hour=hour, minute=minute)
    scheduler.add_job(run_pipeline, trigger=trigger, id="tech_radar_weekly")

    logger.info(
        "Scheduler started — will run every %s at %s (local time). Press Ctrl+C to stop.",
        weekday.capitalize(),
        time,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    import yaml

    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    sched = config.get("schedule", {})
    start(
        weekday=sched.get("weekday", "monday"),
        time=sched.get("time", "08:00"),
    )
