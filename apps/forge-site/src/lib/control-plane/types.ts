export const TASK_STATUSES = [
  "planning",
  "proposed",
  "claimed",
  "in_progress",
  "review",
  "done",
  "failed",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export const STATUS_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  planning: ["proposed", "failed"],
  proposed: ["claimed", "failed", "planning"],
  claimed: ["in_progress", "failed", "proposed"],
  in_progress: ["review", "failed"],
  review: ["done", "failed", "in_progress"],
  done: [],
  failed: ["proposed", "planning"],
};

export type Artifact = {
  kind: string;
  path: string;
  url?: string;
};

export type FactoryTask = {
  id: string;
  title: string;
  goal: string;
  acceptance_criteria: string[];
  sandbox_profile: string;
  repo_path: string;
  status: TaskStatus;
  assignee_agent: string | null;
  artifacts: Artifact[];
  risk_level: string;
  branch: string | null;
  worker_hook: string | null;
  notes: string | null;
  github_project_item_id: string | null;
  budget_minutes: number;
  claimed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskMessage = {
  id: string;
  task_id: string;
  source: string;
  author: string | null;
  body: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type JobKind = "plan" | "implement" | "notify" | "sync-projects";

export type ControlAction = "approve" | "cancel" | "retry";

export function canTransition(from: TaskStatus, to: TaskStatus): boolean {
  if (from === to) return true;
  return STATUS_TRANSITIONS[from]?.includes(to) ?? false;
}

export function rowToTask(row: Record<string, unknown>): FactoryTask {
  return {
    id: String(row.id),
    title: String(row.title),
    goal: String(row.goal),
    acceptance_criteria: Array.isArray(row.acceptance_criteria)
      ? (row.acceptance_criteria as string[])
      : [],
    sandbox_profile: String(row.sandbox_profile),
    repo_path: String(row.repo_path),
    status: row.status as TaskStatus,
    assignee_agent:
      row.assignee_agent === null || row.assignee_agent === undefined
        ? null
        : String(row.assignee_agent),
    artifacts: Array.isArray(row.artifacts) ? (row.artifacts as Artifact[]) : [],
    risk_level: String(row.risk_level),
    branch: row.branch ? String(row.branch) : null,
    worker_hook: row.worker_hook ? String(row.worker_hook) : null,
    notes: row.notes ? String(row.notes) : null,
    github_project_item_id: row.github_project_item_id
      ? String(row.github_project_item_id)
      : null,
    budget_minutes: Number(row.budget_minutes ?? 30),
    claimed_at: row.claimed_at ? String(row.claimed_at) : null,
    created_at: String(row.created_at),
    updated_at: String(row.updated_at),
  };
}

export function rowToMessage(row: Record<string, unknown>): TaskMessage {
  return {
    id: String(row.id),
    task_id: String(row.task_id),
    source: String(row.source),
    author: row.author ? String(row.author) : null,
    body: String(row.body),
    metadata:
      row.metadata && typeof row.metadata === "object"
        ? (row.metadata as Record<string, unknown>)
        : {},
    created_at: String(row.created_at),
  };
}
