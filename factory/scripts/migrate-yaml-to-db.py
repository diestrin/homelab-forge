#!/usr/bin/env python3
"""One-time migration: factory/tasks/*.yaml → control plane Postgres via API."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

from control_plane_client import ControlPlaneError, create_task, is_configured, list_tasks


def load_yaml(path: Path) -> dict:
    if yaml is None:
        raise SystemExit("PyYAML required: pip install pyyaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be mapping")
    return data


def main() -> int:
    p = argparse.ArgumentParser(description="Migrate git task YAML to control plane DB")
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if not is_configured():
        print("Set FORGE_CONTROL_PLANE_URL and FORGE_API_TOKEN", file=sys.stderr)
        return 1

    tasks_dir = args.repo / "factory" / "tasks"
    existing = {t["id"] for t in list_tasks()}
    migrated = 0

    for path in sorted(tasks_dir.glob("TASK-*.yaml")):
        data = load_yaml(path)
        tid = str(data.get("id") or "")
        if not tid:
            print(f"skip {path.name}: no id", file=sys.stderr)
            continue
        if tid in existing:
            print(f"skip {tid}: already in DB")
            continue
        ac = data.get("acceptance_criteria") or []
        if not isinstance(ac, list):
            ac = [str(ac)]
        payload = {
            "id": tid,
            "title": data.get("title") or tid,
            "goal": data.get("goal") or "",
            "acceptance_criteria": [str(x) for x in ac],
            "sandbox_profile": data.get("sandbox_profile") or "agent-cell",
            "repo_path": data.get("repo_path") or ".",
            "status": data.get("status") or "done",
            "risk_level": data.get("risk_level") or "low",
            "branch": data.get("branch"),
            "worker_hook": data.get("worker_hook"),
            "notes": data.get("notes"),
            "budget_minutes": data.get("budget_minutes") or 30,
            "initial_message": f"Migrated from git YAML: {path.name}",
            "message_source": "system",
        }
        if args.dry_run:
            print(f"would migrate {tid} status={payload['status']}")
            migrated += 1
            continue
        try:
            create_task(payload)
            print(f"migrated {tid}")
            migrated += 1
        except ControlPlaneError as err:
            print(f"fail {tid}: {err}", file=sys.stderr)

    print(f"done: {migrated} task(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
