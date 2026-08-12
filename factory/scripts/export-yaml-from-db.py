#!/usr/bin/env python3
"""Optional export: control plane Postgres → factory/tasks/*.yaml mirror (ADR-010)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parent))

from control_plane_client import is_configured, list_tasks  # noqa: E402


def task_to_yaml(task: dict) -> dict:
    return {
        "id": task["id"],
        "title": task["title"],
        "goal": task["goal"],
        "acceptance_criteria": task.get("acceptance_criteria") or [],
        "sandbox_profile": task.get("sandbox_profile") or "agent-cell",
        "repo_path": task.get("repo_path") or ".",
        "status": task.get("status") or "planning",
        "assignee_agent": task.get("assignee_agent"),
        "artifacts": task.get("artifacts") or [],
        "risk_level": task.get("risk_level") or "low",
        "branch": task.get("branch"),
        "worker_hook": task.get("worker_hook"),
        "notes": task.get("notes") or "",
        "budget_minutes": task.get("budget_minutes") or 30,
        "claimed_at": task.get("claimed_at"),
        "updated_at": task.get("updated_at"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Export DB tasks to git YAML mirror")
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if yaml is None:
        print("PyYAML required", file=sys.stderr)
        return 1
    if not is_configured():
        print("Set FORGE_CONTROL_PLANE_URL and FORGE_API_TOKEN", file=sys.stderr)
        return 1

    out_dir = args.repo / "factory" / "tasks"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for task in list_tasks():
        tid = str(task["id"])
        slug = tid.lower()
        path = out_dir / f"{tid}-export.yaml"
        doc = task_to_yaml(task)
        if args.dry_run:
            print(f"would write {path}")
        else:
            path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
            print(f"wrote {path}")
        count += 1
    print(f"exported {count} task(s) — mirror only; Postgres is runtime SoT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
