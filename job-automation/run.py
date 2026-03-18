#!/usr/bin/env python3
"""
Job Application Platform — CLI runner.

Usage:
  python run.py api          # Start the backend API server
  python run.py scrape       # Run scraper once
  python run.py scrape --live # Run scraper (save results)
  python run.py pipeline     # Run full pipeline (scrape + match + notify)
  python run.py init-db      # Initialise the database
  python run.py notify-test  # Send a test notification
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run")


def cmd_api(args):
    """Start the FastAPI backend."""
    import uvicorn
    import yaml
    with open("config/settings.yaml") as f:
        settings = yaml.safe_load(f)
    logger.info("Starting API server...")
    uvicorn.run(
        "backend.main:app",
        host=settings["backend"]["host"],
        port=settings["backend"]["port"],
        reload=args.debug,
        log_level="debug" if args.debug else "info",
    )


def cmd_init_db(args):
    """Initialise the database schema."""
    from database.db import init_db
    init_db()
    logger.info("Database initialised successfully.")


def cmd_scrape(args):
    """Run the scraper."""
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    from scrapers.scraper_manager import ScraperManager
    manager = ScraperManager()
    dry_run = not args.live
    logger.info(f"Running scraper (dry_run={dry_run})")
    summary = manager.run(dry_run=dry_run)
    logger.info(f"Scrape complete: {summary}")


def cmd_pipeline(args):
    """Run full pipeline."""
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    from automation.orchestrator import Orchestrator
    orch = Orchestrator()
    results = orch.run_full_pipeline()
    logger.info(f"Pipeline complete: {results}")


def cmd_notify_test(args):
    """Send a test notification."""
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    from notifications.notifier import Notifier
    notifier = Notifier()
    notifier.notify_high_match(
        job_title="Sustainability Policy Analyst",
        company="Carbon Disclosure Project",
        url="https://www.cdp.net/en/careers",
        score=92.5,
    )
    logger.info("Test notification sent.")


def main():
    parser = argparse.ArgumentParser(
        description="Job Application Platform CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # api
    api_parser = sub.add_parser("api", help="Start the backend API")
    api_parser.add_argument("--debug", action="store_true", help="Enable hot reload")
    api_parser.set_defaults(func=cmd_api)

    # init-db
    init_parser = sub.add_parser("init-db", help="Initialise the database")
    init_parser.set_defaults(func=cmd_init_db)

    # scrape
    scrape_parser = sub.add_parser("scrape", help="Run the scraper")
    scrape_parser.add_argument("--live", action="store_true", help="Save results (default: dry run)")
    scrape_parser.set_defaults(func=cmd_scrape)

    # pipeline
    pipe_parser = sub.add_parser("pipeline", help="Run full pipeline")
    pipe_parser.set_defaults(func=cmd_pipeline)

    # notify-test
    notify_parser = sub.add_parser("notify-test", help="Send a test notification")
    notify_parser.set_defaults(func=cmd_notify_test)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
