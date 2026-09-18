"""Nightly connector pulls, plus a nightly budget-check safety net.

Each configured provider connector is asked for yesterday's usage; a connector
reporting supports_usage_pull=False (missing credentials, or a probe that
detected the API is unavailable) is skipped without error -- it's expected
that not every provider has a working connector.

Budget thresholds are normally checked immediately after every ingestion (CSV
import, connector pull, manual allocation reprice) -- see the callers of
evaluate_all_active_budgets(). The nightly run here is a safety net for the
case where every connector pull was skipped (nothing to trigger the inline
check) or some other ingestion path was missed.

Started from app.main's lifespan; safe to run with zero configured connectors
and zero budgets (it will just skip/no-op every night until configured).
"""

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.connectors.base import ConnectorUnavailableError
from app.connectors.registry import get_connector
from app.db.session import SessionLocal
from app.models.provider import Provider
from app.services.budget_engine import evaluate_all_active_budgets
from app.services.ingestion_service import run_connector_pull

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_nightly_pulls() -> None:
    yesterday = date.today() - timedelta(days=1)
    db = SessionLocal()
    try:
        for provider in db.query(Provider).all():
            connector = get_connector(provider.code.value)
            if connector is None:
                continue
            if not connector.capabilities().supports_usage_pull:
                continue
            try:
                result = run_connector_pull(db, provider.code.value, yesterday, yesterday)
                logger.info("Nightly pull for %s: %s", provider.code.value, result)
            except ConnectorUnavailableError as exc:
                logger.warning("Nightly pull for %s skipped: %s", provider.code.value, exc)
            except Exception:
                logger.exception("Nightly pull for %s failed", provider.code.value)
    finally:
        db.close()


def run_nightly_budget_check() -> None:
    db = SessionLocal()
    try:
        new_alerts = evaluate_all_active_budgets(db)
        if new_alerts:
            logger.info("Nightly budget check fired %d new alert(s)", len(new_alerts))
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(run_nightly_pulls, "cron", hour=2, minute=0, id="nightly_connector_pulls")
    _scheduler.add_job(run_nightly_budget_check, "cron", hour=2, minute=30, id="nightly_budget_check")
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
