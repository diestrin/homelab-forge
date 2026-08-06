from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULT_CONFIG_DIR, load_config
from .scanner import format_report, report_as_dict, run_scan


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="host-watch",
        description="Scan for suspicious processes, listeners, and remote peers.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="Directory containing config.toml and allowlists.toml",
    )
    p.add_argument("--config", type=Path, help="Override config.toml path")
    p.add_argument("--allowlists", type=Path, help="Override allowlists.toml path")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run checks but do not send notifications",
    )
    p.add_argument(
        "--no-notify",
        action="store_true",
        help="Skip notifications (still updates state)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON report",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    cfg = load_config(
        config_dir=args.config_dir,
        config_path=args.config,
        allowlists_path=args.allowlists,
    )

    level = logging.WARNING
    if args.verbose >= 2 or cfg.log_level == "debug":
        level = logging.DEBUG
    elif args.verbose == 1 or cfg.log_level == "info":
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not (args.config_dir / "allowlists.toml").exists() and not args.allowlists:
        # Fall back to example allowlists shipped with the repo when developing.
        repo_example = Path(__file__).resolve().parents[1] / "config" / "allowlists.example.toml"
        if repo_example.exists():
            logging.getLogger(__name__).warning(
                "No allowlists.toml in %s — using bundled example %s",
                args.config_dir,
                repo_example,
            )
            cfg = load_config(
                config_dir=args.config_dir,
                config_path=args.config,
                allowlists_path=repo_example,
            )

    report = run_scan(
        cfg,
        dry_run=args.dry_run,
        notify=not args.no_notify and not args.dry_run,
    )

    if args.json:
        print(json.dumps(report_as_dict(report), indent=2))
    else:
        print(format_report(report))

    # Exit 1 only when there are *new* findings (useful for timers / CI).
    return 1 if report.new_findings else 0


if __name__ == "__main__":
    sys.exit(main())
