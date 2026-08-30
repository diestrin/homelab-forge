#!/usr/bin/env bash
# Local mirror of the CI checks that need no GitHub-hosted secrets (TASK-011).
# Factory agents MUST run this before every push that updates a factory PR.
#
# Mirrors .github/workflows/ci.yml:
#   markdown-lint    → markdownlint-cli2 (required; config .markdownlint-cli2.yaml)
#   factory-schema   → ./forge factory validate (required; python3)
#   shell lint       → all *.sh + forge + bootstrap (if installed)
#   actionlint       → workflow lint (if installed)
#   kube-manifests   → kustomize + kubeconform (if installed)
#   nix-flake-check  → opt-in via FORGE_LINT_NIX=1 (slow)
#
# Usage: lint-local.sh [--fix]   (run from the repo/worktree root)
set -uo pipefail

FIX=0
[[ "${1:-}" == "--fix" ]] && FIX=1

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 1

FAILED=0
declare -a SUMMARY=()

note() { printf 'lint-local: %s\n' "$*"; }
run_check() {
  local name="$1"
  shift
  note "==> $name"
  if "$@"; then
    SUMMARY+=("ok   $name")
  else
    SUMMARY+=("FAIL $name")
    FAILED=1
  fi
}

# markdownlint-cli2 — required (MD047 on TASK-009 is exactly what this gate is for).
markdown_lint() {
  local -a fix_arg=()
  [[ "$FIX" -eq 1 ]] && fix_arg=(--fix)
  if command -v markdownlint-cli2 >/dev/null 2>&1; then
    markdownlint-cli2 "${fix_arg[@]}" "**/*.md"
  elif command -v npx >/dev/null 2>&1; then
    npx --yes markdownlint-cli2 "${fix_arg[@]}" "**/*.md"
  else
    note "markdownlint-cli2 unavailable (install: npm i -g markdownlint-cli2) — REQUIRED"
    return 1
  fi
}
run_check "markdownlint-cli2" markdown_lint

# factory task schema — required (python3 is a worker prerequisite).
run_check "forge factory validate" ./forge factory validate

# Shell lint — same file set as CI.
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck_all() {
    { git ls-files '*.sh'; echo forge; echo bootstrap; } \
      | xargs shellcheck --severity=warning
  }
  run_check "shellcheck" shellcheck_all
else
  note "skip shellcheck (not installed)"
fi

# actionlint — workflow lint.
if command -v actionlint >/dev/null 2>&1; then
  run_check "actionlint" actionlint
else
  note "skip actionlint (not installed)"
fi

# kustomize build + kubeconform — same loop as CI.
if command -v kubectl >/dev/null 2>&1 && command -v kubeconform >/dev/null 2>&1; then
  kube_manifests() {
    local status=0 dir
    for dir in $(git ls-files 'k8s/**/kustomization.yaml' | xargs -n1 dirname | sort); do
      note "kustomize $dir"
      kubectl kustomize "$dir" \
        | kubeconform -strict -ignore-missing-schemas -summary || status=1
    done
    return "$status"
  }
  run_check "kube-manifests" kube_manifests
else
  note "skip kube-manifests (kubectl/kubeconform not installed)"
fi

# nix flake check — opt-in (slow eval).
if [[ "${FORGE_LINT_NIX:-0}" == "1" ]] && command -v nix >/dev/null 2>&1; then
  run_check "nix flake check" nix flake check ./nix --no-build
fi

echo
note "summary:"
for line in "${SUMMARY[@]}"; do
  note "  $line"
done
exit "$FAILED"
