"""The alert-processing service: evaluates scheduled alert rules every minute (APScheduler).

Runs as the locked 'system' account (migration 0010), which holds ADMIN so row-level security shows it every
branch and brand; its writes are audited with source 'System'. Run exactly one instance (the TrishulJobs
Windows service): the database's unique index still prevents duplicate alerts if two ever overlap.

    uv run trishul-jobs            run until stopped
    uv run trishul-jobs --once     one pass, then exit (diagnostics)
"""

import argparse
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from trishul_api.config import get_settings
from trishul_api.db import set_audit_context, user_session
from trishul_api.db.engine import create_db_engine
from trishul_api.db.models import AppUser
from trishul_api.modules.alerts.engine import AlertEngine, RunSummary
from trishul_api.modules.alerts.recipients import SYSTEM_USERNAME
from trishul_api.secrets import create_secret_provider

log = logging.getLogger("trishul_api.jobs")


def system_user_id(engine: Engine) -> int:
    with Session(engine) as session:  # core.app_user is not filtered by row-level security
        user_id = session.scalar(select(AppUser.id).where(AppUser.username == SYSTEM_USERNAME))
    if user_id is None:
        raise RuntimeError("The 'system' user is missing: run the database migrations (alembic upgrade head).")
    return user_id


def process_alerts(engine: Engine, user_id: int) -> RunSummary:
    """One pass over every active alert rule."""
    with user_session(engine, user_id) as session:
        set_audit_context(session, user_id=user_id, source="System", ip_address=None)
        summary = AlertEngine(session).run_scheduled()
    failed = [r for r in summary.rules if r.error]
    log.info(
        "Alert pass: %d rules, %d raised, %d resolved, %d failed",
        len(summary.rules),
        summary.raised,
        summary.resolved,
        len(failed),
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Trishul background jobs (alert processing).")
    parser.add_argument("--once", action="store_true", help="run one pass and exit")
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    engine = create_db_engine(settings, create_secret_provider(settings))
    user_id = system_user_id(engine)

    if args.once:
        process_alerts(engine, user_id)
        return

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        process_alerts,
        "interval",
        seconds=settings.alert_job_interval_seconds,
        args=[engine, user_id],
        id="alerts",
        max_instances=1,  # a slow pass is never overlapped by the next one
        coalesce=True,
        next_run_time=None,
    )
    log.info("TrishulJobs started: alerts every %ss", settings.alert_job_interval_seconds)
    process_alerts(engine, user_id)  # first pass straight away
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("TrishulJobs stopped")


if __name__ == "__main__":
    main()
