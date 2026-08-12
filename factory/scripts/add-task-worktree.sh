#!/usr/bin/env bash
# Add (or reuse) a factory task worktree without stealing another checkout's branch.
# If BRANCH is already checked out elsewhere (e.g. operator Cursor clone), add a
# detached worktree at START so the worker/orchestrator can still commit + push
# with HEAD:refs/heads/BRANCH.
#
# usage: add-task-worktree.sh <repo> <worktree-path> <branch> [start-point]
set -euo pipefail

REPO="${1:-}"
WT="${2:-}"
BRANCH="${3:-}"
START="${4:-}"

die() { echo "add-task-worktree: $*" >&2; exit 1; }
[[ -n "$REPO" && -n "$WT" && -n "$BRANCH" ]] || die "usage: $0 <repo> <worktree-path> <branch> [start-point]"
command -v git >/dev/null || die "git required"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null || die "not a git repo: $REPO"

if [[ -d "$WT" ]]; then
  echo "reuse $WT"
  exit 0
fi

git -C "$REPO" fetch origin --prune >/dev/null 2>&1 || true

if [[ -z "$START" ]]; then
  if git -C "$REPO" rev-parse --verify "origin/${BRANCH}" >/dev/null 2>&1; then
    START="origin/${BRANCH}"
  elif git -C "$REPO" rev-parse --verify "origin/main" >/dev/null 2>&1; then
    START="origin/main"
  else
    START="main"
  fi
fi

err="$(mktemp)"
trap 'rm -f "$err"' EXIT

if git -C "$REPO" worktree add -B "$BRANCH" "$WT" "$START" >/dev/null 2>"$err"; then
  echo "branch $WT"
  exit 0
fi

if grep -qiE 'already.*(used|checked out)|is already used by worktree' "$err"; then
  echo "add-task-worktree: $BRANCH in use elsewhere; detached worktree at $START" >&2
  git -C "$REPO" worktree add --detach "$WT" "$START"
  echo "detached $WT"
  exit 0
fi

cat "$err" >&2
die "worktree add failed"
