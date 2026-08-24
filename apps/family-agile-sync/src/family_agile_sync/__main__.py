"""CLI entrypoint. One subcommand per CronJob."""

from __future__ import annotations

import argparse
import logging
import sys

from .config import Config
from .jobs import close_cycle, pull_completions, push_definitions, reconcile

JOBS = {
    "push-definitions": push_definitions.run,
    "pull-completions": pull_completions.run,
    "reconcile": reconcile.run,
    "close-cycle": close_cycle.run,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="family-agile-sync")
    parser.add_argument("job", choices=sorted(JOBS))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = Config.from_env()
    except RuntimeError as exc:
        logging.error("%s", exc)
        return 2

    if config.dry_run:
        logging.warning("DRY_RUN enabled: no writes will be performed")

    try:
        JOBS[args.job](config)
    except Exception:
        logging.exception("job %s failed", args.job)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
