#!/usr/bin/env python3
"""
Scheduler for running the AI trading pipeline at configurable intervals.

Job schedule:
  Every 15 min  — exit_monitor.run_exit_checks() (runs BEFORE analysis)
  Every 15 min  — analysis pipeline per symbol
  Daily 15:30   — pnl_calculator.take_snapshot()

Kill switch blocks entry, NOT exit. Exit monitor always runs.
"""
import time
import schedule
from dotenv import load_dotenv
load_dotenv()

from main import run
from portfolio.exit_monitor import run_exit_checks
from portfolio.pnl_calculator import take_snapshot
from safety.kill_switch import check_and_halt_if_degraded
from utils.logger import setup_logger
from config import Config

logger = setup_logger(__name__)


def exit_job():
    """Run exit checks for all open positions."""
    logger.info("[SCHEDULER] Running exit monitor")
    result = run_exit_checks()
    logger.info(
        f"[SCHEDULER] Exit monitor done: "
        f"checked={result['checked']} exited={result['exited']} errors={result['errors']}"
    )


def degradation_check_job():
    """Check model health; activate kill switch if degraded."""
    halted = check_and_halt_if_degraded()
    if halted:
        logger.critical(
            "[SCHEDULER] Model degradation detected — trading halted. "
            "Manual /resume required after investigation."
        )


def analysis_job(symbol):
    """Run the full analysis pipeline for a symbol."""
    # Skip if kill switch is active (including auto-halt from degradation check)
    from safety.kill_switch import is_trading_halted
    if is_trading_halted():
        logger.warning(f"[SCHEDULER] Kill switch active — skipping analysis for {symbol}")
        return
    logger.info(f"[SCHEDULER] Starting analysis job for: {symbol}")
    result = run(symbol)
    logger.info(
        f"[SCHEDULER] Analysis done for {symbol}: "
        f"{result.get('decision', 'ERROR')}"
    )


def snapshot_job():
    """Take daily P&L snapshot at market close."""
    logger.info("[SCHEDULER] Taking daily P&L snapshot")
    ok = take_snapshot()
    logger.info(f"[SCHEDULER] Snapshot {'saved' if ok else 'FAILED'}")


def log_retention_job():
    """Delete aged rows from ephemeral log tables (runs at 02:00 IST)."""
    logger.info("[SCHEDULER] Running log retention")
    try:
        from maintenance.log_retention import run_retention
        result = run_retention()
        logger.info(
            f"[SCHEDULER] Log retention done — "
            f"audit_log={result['audit_log_deleted']} "
            f"pipeline_metrics={result['pipeline_metrics_deleted']} "
            f"llm_calls={result['llm_calls_deleted']} "
            f"rate_limit={result['rate_limit_deleted']}"
        )
    except Exception as e:
        logger.error(f"[SCHEDULER] log_retention_job error: {e}")


def db_cleanup_job():
    """ANALYZE tables and reset stale backtest runs (runs at 03:00 IST)."""
    logger.info("[SCHEDULER] Running DB cleanup")
    try:
        from maintenance.db_cleanup import run_all
        result = run_all()
        logger.info(
            f"[SCHEDULER] DB cleanup done — "
            f"vacuum_ok={result['vacuum_ok']} "
            f"stale_runs_reset={result['stale_runs_reset']} "
            f"idem_keys_purged={result['idempotency_keys_purged']}"
        )
    except Exception as e:
        logger.error(f"[SCHEDULER] db_cleanup_job error: {e}")


def run_scheduler():
    """Set up and run the scheduler."""
    symbols = getattr(Config, 'SYMBOLS', ['RELIANCE.NS'])

    # Degradation check — runs every 15 min, BEFORE analysis
    schedule.every(15).minutes.do(degradation_check_job)

    # Exit monitor — runs every 15 min, BEFORE analysis
    schedule.every(15).minutes.do(exit_job)

    # Analysis pipeline — per symbol, every 15 min
    for symbol in symbols:
        schedule.every(15).minutes.do(analysis_job, symbol)
        logger.info(f"[SCHEDULER] Scheduled analysis for {symbol} every 15 minutes")

    # Daily P&L snapshot at market close (15:30 IST)
    schedule.every().day.at("15:30").do(snapshot_job)
    logger.info("[SCHEDULER] Scheduled daily P&L snapshot at 15:30 IST")

    # Maintenance jobs (IST times as UTC offset: IST = UTC+5:30)
    # 02:00 IST = 20:30 UTC previous day — use UTC times for schedule
    schedule.every().day.at("20:30").do(log_retention_job)
    logger.info("[SCHEDULER] Scheduled log retention at 02:00 IST (20:30 UTC)")

    # 03:00 IST = 21:30 UTC previous day
    schedule.every().day.at("21:30").do(db_cleanup_job)
    logger.info("[SCHEDULER] Scheduled DB cleanup at 03:00 IST (21:30 UTC)")

    # Run once immediately at startup
    degradation_check_job()
    exit_job()
    for symbol in symbols:
        analysis_job(symbol)

    logger.info("[SCHEDULER] Scheduler running. Press Ctrl+C to exit.")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler()
