#!/usr/bin/env python3
"""YAML task helpers for the forge factory (ADR-004). No PyYAML required — uses a tiny subset parser via ruamel if present, else PyYAML, else a constrained loader."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

STATUSES = (
    "planning",
    "proposed",
    "claimed",
    "in_progress",
    "review",
    "done",
    "failed",
)
TRANSITIONS = {
    # planning = plan PR open; not claimable until Slack/CLI approve → proposed
    "planning": {"proposed", "failed"},
    "proposed": {"claimed", "failed", "planning"},  # planning = send back to plan
    "claimed": {"in_progress", "failed", "proposed"},  # proposed = release lease
    "in_progress": {"review", "failed"},
    "review": {"done", "failed", "in_progress"},
    "done": set(),
    "failed": {"proposed", "planning"},
}

REQUIRED = (
    "id",
    "title",
    "goal",
    "acceptance_criteria",
    "sandbox_profile",
    "repo_path",
    "status",
    "risk_level",
)

PROFILES = ("trusted", "devcontainer", "incus", "k8s-workload", "agent-cell")
RISKS = ("low", "medium", "high")

STATUS_TO_PROJECT_COLUMN = {
    "planning": "Planning",
    "proposed": "Proposed",
    "claimed": "Claimed",
    "in_progress": "In Progress",
    "review": "Review",
    "done": "Done",
    "failed": "Failed",
}


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: root must be a mapping")
        return data
    # Minimal fallback for our flat task files (no nested structures beyond lists of scalars/objects).
    return _minimal_yaml_load(text, path)


def dump_yaml(data: dict) -> str:
    if yaml is not None:
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return _minimal_yaml_dump(data)


def _minimal_yaml_load(text: str, path: Path) -> dict:
    """Very small YAML subset sufficient for factory task files."""
    data: dict = {}
    lines = text.splitlines()
    i = 0
    key_re = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        m = key_re.match(line)
        if not m:
            raise ValueError(f"{path}:{i+1}: unsupported YAML line: {line}")
        key, rest = m.group(1), m.group(2)
        if rest == "" or rest == "|" or rest == ">":
            # block or nested — only support list under key
            i += 1
            if i < len(lines) and lines[i].startswith("  - "):
                items = []
                while i < len(lines) and lines[i].startswith("  - "):
                    item = lines[i][4:].strip()
                    if item.startswith("{") or (i + 1 < len(lines) and lines[i + 1].startswith("    ")):
                        # artifact object spanning lines
                        obj = {}
                        if item.startswith("{") and item.endswith("}"):
                            # inline not supported in fallback
                            raise ValueError(f"{path}:{i+1}: install PyYAML for complex artifacts")
                        # multi-line mapping under list item
                        while i < len(lines):
                            if lines[i].startswith("  - "):
                                first = lines[i][4:].strip()
                                if first:
                                    km = key_re.match(first)
                                    if km:
                                        obj[km.group(1)] = _parse_scalar(km.group(2))
                                i += 1
                                while i < len(lines) and lines[i].startswith("    "):
                                    km = key_re.match(lines[i].strip())
                                    if not km:
                                        raise ValueError(f"{path}:{i+1}: bad artifact field")
                                    obj[km.group(1)] = _parse_scalar(km.group(2))
                                    i += 1
                                items.append(obj)
                                obj = {}
                                continue
                            break
                        data[key] = items
                        continue
                    items.append(_parse_scalar(item))
                    i += 1
                data[key] = items
                continue
            # folded string block
            parts = []
            while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                if lines[i].strip():
                    parts.append(lines[i].strip())
                i += 1
            data[key] = " ".join(parts) if rest == ">" else "\n".join(parts)
            continue
        data[key] = _parse_scalar(rest)
        i += 1
    return data


def _parse_scalar(s: str):
    if s in ("null", "~", ""):
        return None
    if s in ("true", "false"):
        return s == "true"
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return s


def _minimal_yaml_dump(data: dict) -> str:
    out = []
    for k, v in data.items():
        if v is None:
            out.append(f"{k}: null")
        elif isinstance(v, bool):
            out.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            out.append(f"{k}: {v}")
        elif isinstance(v, list):
            out.append(f"{k}:")
            for item in v:
                if isinstance(item, dict):
                    out.append("  - " + dump_flowish(item))
                else:
                    out.append(f"  - {_quote(item)}")
        elif isinstance(v, str) and ("\n" in v or len(v) > 80):
            out.append(f"{k}: |")
            for line in v.splitlines() or [""]:
                out.append(f"  {line}")
        else:
            out.append(f"{k}: {_quote(v)}")
    return "\n".join(out) + "\n"


def dump_flowish(d: dict) -> str:
    # multi-line mapping style
    keys = list(d.keys())
    if not keys:
        return "{}"
    first = keys[0]
    lines = [f"{first}: {_quote(d[first])}"]
    for k in keys[1:]:
        lines.append(f"\n    {k}: {_quote(d[k])}")
    return "".join(lines)


def _quote(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    s = str(v)
    if s == "" or any(c in s for c in ":#{}[]&*?|>!%@`,'\"") or s.strip() != s:
        return json.dumps(s)
    return s


def validate(data: dict, path: Path | None = None) -> list[str]:
    errors = []
    loc = str(path) if path else "task"
    for key in REQUIRED:
        if key not in data or data[key] in (None, "", []):
            errors.append(f"{loc}: missing required field '{key}'")
    if "id" in data and not re.fullmatch(r"TASK-[0-9]{3,}", str(data["id"])):
        errors.append(f"{loc}: id must match TASK-NNN")
    if data.get("status") not in STATUSES:
        errors.append(f"{loc}: invalid status {data.get('status')!r}")
    if data.get("sandbox_profile") not in PROFILES:
        errors.append(f"{loc}: invalid sandbox_profile {data.get('sandbox_profile')!r}")
    if data.get("risk_level") not in RISKS:
        errors.append(f"{loc}: invalid risk_level {data.get('risk_level')!r}")
    ac = data.get("acceptance_criteria")
    if not isinstance(ac, list) or not ac:
        errors.append(f"{loc}: acceptance_criteria must be a non-empty list")
    return errors


def save(path: Path, data: dict) -> None:
    data["updated_at"] = utcnow()
    path.write_text(dump_yaml(data), encoding="utf-8")


def transition(data: dict, new_status: str) -> None:
    cur = data.get("status")
    if new_status not in STATUSES:
        raise ValueError(f"invalid status: {new_status}")
    if new_status != cur and new_status not in TRANSITIONS.get(cur, set()):
        raise ValueError(f"illegal transition {cur} → {new_status}")
    data["status"] = new_status


def tasks_dir(repo: Path) -> Path:
    return repo / "factory" / "tasks"


def iter_tasks(repo: Path):
    d = tasks_dir(repo)
    for path in sorted(d.glob("TASK-*.yaml")):
        yield path, load_yaml(path)


def cmd_validate(repo: Path) -> int:
    errs = []
    for path, data in iter_tasks(repo):
        errs.extend(validate(data, path))
        if data.get("id") and path.name != f"{data['id']}.yaml" and not path.name.startswith(data["id"]):
            # allow TASK-001-slug.yaml
            if not path.name.startswith(str(data["id"])):
                errs.append(f"{path}: filename should start with {data['id']}")
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    print("ok: all tasks valid")
    return 0


def cmd_list(repo: Path) -> int:
    for path, data in iter_tasks(repo):
        print(f"{data.get('id')}\t{data.get('status')}\t{data.get('title')}\t{path.name}")
    return 0


def cmd_get(repo: Path, task_id: str) -> int:
    for path, data in iter_tasks(repo):
        if data.get("id") == task_id:
            print(dump_yaml(data), end="")
            return 0
    print(f"task not found: {task_id}", file=sys.stderr)
    return 1


def cmd_set_status(repo: Path, task_id: str, status: str, assignee: str | None) -> int:
    for path, data in iter_tasks(repo):
        if data.get("id") != task_id:
            continue
        errs = validate(data, path)
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 1
        try:
            transition(data, status)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        if assignee is not None:
            data["assignee_agent"] = assignee or None
        if status == "claimed":
            data["claimed_at"] = utcnow()
        if status in ("proposed", "planning"):
            data["assignee_agent"] = None
            data["claimed_at"] = None
        save(path, data)
        print(f"{task_id} → {status}")
        return 0
    print(f"task not found: {task_id}", file=sys.stderr)
    return 1


def cmd_approve(repo: Path, task_id: str) -> int:
    """Slack/CLI gate: planning → proposed (worker-claimable)."""
    return cmd_set_status(repo, task_id, "proposed", assignee=None)


def cmd_claim(repo: Path, task_id: str | None, worker: str) -> int:
    candidates = []
    for path, data in iter_tasks(repo):
        if task_id and data.get("id") != task_id:
            continue
        if data.get("status") == "proposed":
            candidates.append((path, data))
    if not candidates:
        print("no proposed tasks to claim", file=sys.stderr)
        return 2
    path, data = candidates[0]
    transition(data, "claimed")
    data["assignee_agent"] = worker
    data["claimed_at"] = utcnow()
    save(path, data)
    print(data["id"])
    print(path)
    return 0


def cmd_next_id(repo: Path) -> int:
    max_n = 0
    for _path, data in iter_tasks(repo):
        tid = str(data.get("id") or "")
        m = re.match(r"^TASK-(\d+)$", tid)
        if m:
            max_n = max(max_n, int(m.group(1)))
    print(f"TASK-{max_n + 1:03d}")
    return 0


def cmd_add_artifact(repo: Path, task_id: str, kind: str, path_str: str, url: str | None) -> int:
    for path, data in iter_tasks(repo):
        if data.get("id") != task_id:
            continue
        arts = data.setdefault("artifacts", [])
        item = {"kind": kind, "path": path_str}
        if url:
            item["url"] = url
        arts.append(item)
        save(path, data)
        print(f"artifact added to {task_id}")
        return 0
    print(f"task not found: {task_id}", file=sys.stderr)
    return 1


def cmd_column(status: str) -> int:
    col = STATUS_TO_PROJECT_COLUMN.get(status)
    if not col:
        print(f"unknown status: {status}", file=sys.stderr)
        return 1
    print(col)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="forge factory task library")
    p.add_argument("--repo", type=Path, default=Path.cwd())
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate")
    sub.add_parser("list")
    g = sub.add_parser("get")
    g.add_argument("task_id")
    s = sub.add_parser("set-status")
    s.add_argument("task_id")
    s.add_argument("status")
    s.add_argument("--assignee", default=None)
    ap = sub.add_parser("approve")
    ap.add_argument("task_id")
    c = sub.add_parser("claim")
    c.add_argument("--task", default=None)
    c.add_argument("--worker", required=True)
    sub.add_parser("next-id")
    a = sub.add_parser("add-artifact")
    a.add_argument("task_id")
    a.add_argument("kind")
    a.add_argument("path")
    a.add_argument("--url", default=None)
    col = sub.add_parser("column")
    col.add_argument("status")
    m = sub.add_parser("map-json")
    # dump status→column map

    args = p.parse_args(argv)
    repo = args.repo.resolve()
    if args.cmd == "validate":
        return cmd_validate(repo)
    if args.cmd == "list":
        return cmd_list(repo)
    if args.cmd == "get":
        return cmd_get(repo, args.task_id)
    if args.cmd == "set-status":
        return cmd_set_status(repo, args.task_id, args.status, args.assignee)
    if args.cmd == "approve":
        return cmd_approve(repo, args.task_id)
    if args.cmd == "claim":
        return cmd_claim(repo, args.task, args.worker)
    if args.cmd == "next-id":
        return cmd_next_id(repo)
    if args.cmd == "add-artifact":
        return cmd_add_artifact(repo, args.task_id, args.kind, args.path, args.url)
    if args.cmd == "column":
        return cmd_column(args.status)
    if args.cmd == "map-json":
        print(json.dumps(STATUS_TO_PROJECT_COLUMN, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
