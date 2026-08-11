---
name: factory-reviewer
description: Review a homelab-forge factory pull request before merge to main. Use when asked to review a factory PR, run the review gate or checklist, or decide whether a TASK-NNN is ready to merge and deploy.
---

# Factory reviewer

Walk `factory/review/CHECKLIST.md` item by item — it is the source of truth
(code/task, deploy path, audit, and merge sections).

## Hard rules

1. Confirm CI is green, including the full-history gitleaks scan, before recommending
   merge. Acceptance criteria in the task YAML must be met or explicitly waived in the PR.
2. Merge to `main` **is** the deploy action: Argo CD syncs from `main` (ADR-008).
   Reject any PR or instruction that applies cluster changes around Argo.
3. Human merge is the default (ADR-004). Summarize findings and the checklist result;
   do not merge without explicit human approval.
4. After merge: `./forge factory set-status TASK-NNN done && ./forge factory sync`,
   and watch the relevant Argo Application reach Synced/Healthy.
