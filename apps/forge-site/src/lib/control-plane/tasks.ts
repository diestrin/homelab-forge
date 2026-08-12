import { query, withTransaction } from "@/lib/db/pool";
import {
  canTransition,
  rowToTask,
  type Artifact,
  type FactoryTask,
  type TaskStatus,
} from "./types";

export type CreateTaskInput = {
  id: string;
  title: string;
  goal: string;
  acceptance_criteria: string[];
  sandbox_profile?: string;
  repo_path?: string;
  status?: TaskStatus;
  risk_level?: string;
  branch?: string | null;
  worker_hook?: string | null;
  notes?: string | null;
  budget_minutes?: number;
};

export type UpdateTaskInput = Partial<{
  title: string;
  goal: string;
  acceptance_criteria: string[];
  status: TaskStatus;
  assignee_agent: string | null;
  artifacts: Artifact[];
  branch: string | null;
  notes: string | null;
  github_project_item_id: string | null;
}>;

export async function listTasks(): Promise<FactoryTask[]> {
  const { rows } = await query("SELECT * FROM tasks ORDER BY id ASC");
  return rows.map((r) => rowToTask(r));
}

export async function getTask(id: string): Promise<FactoryTask | null> {
  const { rows } = await query("SELECT * FROM tasks WHERE id = $1", [id]);
  if (!rows[0]) return null;
  return rowToTask(rows[0]);
}

export async function createTask(input: CreateTaskInput): Promise<FactoryTask> {
  const status = input.status ?? "planning";
  const branch = input.branch ?? `factory/${input.id.toLowerCase()}`;
  const { rows } = await query(
    `INSERT INTO tasks (
      id, title, goal, acceptance_criteria, sandbox_profile, repo_path,
      status, risk_level, branch, worker_hook, notes, budget_minutes
    ) VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9,$10,$11,$12)
    RETURNING *`,
    [
      input.id,
      input.title,
      input.goal,
      JSON.stringify(input.acceptance_criteria),
      input.sandbox_profile ?? "agent-cell",
      input.repo_path ?? ".",
      status,
      input.risk_level ?? "low",
      branch,
      input.worker_hook ?? null,
      input.notes ?? null,
      input.budget_minutes ?? 30,
    ],
  );
  return rowToTask(rows[0]);
}

export async function upsertTask(input: CreateTaskInput & UpdateTaskInput): Promise<FactoryTask> {
  const existing = await getTask(input.id);
  if (!existing) {
    return createTask(input);
  }
  const updated = await updateTask(input.id, {
    title: input.title ?? existing.title,
    goal: input.goal ?? existing.goal,
    acceptance_criteria: input.acceptance_criteria ?? existing.acceptance_criteria,
    status: input.status ?? existing.status,
    assignee_agent: input.assignee_agent,
    branch: input.branch ?? existing.branch,
    notes: input.notes ?? existing.notes,
  });
  return updated;
}

export async function updateTask(id: string, patch: UpdateTaskInput): Promise<FactoryTask> {
  const current = await getTask(id);
  if (!current) throw new Error(`task not found: ${id}`);

  if (patch.status && !canTransition(current.status, patch.status)) {
    throw new Error(`illegal transition ${current.status} → ${patch.status}`);
  }

  const fields: string[] = [];
  const values: unknown[] = [];
  let i = 1;

  const setField = (col: string, val: unknown) => {
    fields.push(`${col} = $${i++}`);
    values.push(val);
  };

  if (patch.title !== undefined) setField("title", patch.title);
  if (patch.goal !== undefined) setField("goal", patch.goal);
  if (patch.acceptance_criteria !== undefined) {
    setField("acceptance_criteria", JSON.stringify(patch.acceptance_criteria));
  }
  if (patch.status !== undefined) setField("status", patch.status);
  if (patch.assignee_agent !== undefined) setField("assignee_agent", patch.assignee_agent);
  if (patch.artifacts !== undefined) setField("artifacts", JSON.stringify(patch.artifacts));
  if (patch.branch !== undefined) setField("branch", patch.branch);
  if (patch.notes !== undefined) setField("notes", patch.notes);
  if (patch.github_project_item_id !== undefined) {
    setField("github_project_item_id", patch.github_project_item_id);
  }

  if (patch.status === "claimed") {
    setField("claimed_at", new Date().toISOString());
  }
  if (patch.status === "proposed" || patch.status === "planning") {
    setField("assignee_agent", null);
    setField("claimed_at", null);
  }

  setField("updated_at", new Date().toISOString());
  values.push(id);

  const { rows } = await query(
    `UPDATE tasks SET ${fields.join(", ")} WHERE id = $${i} RETURNING *`,
    values,
  );
  return rowToTask(rows[0]);
}

export async function addArtifact(
  id: string,
  artifact: Artifact,
): Promise<FactoryTask> {
  const current = await getTask(id);
  if (!current) throw new Error(`task not found: ${id}`);
  const artifacts = [...current.artifacts, artifact];
  return updateTask(id, { artifacts });
}

export async function claimTask(taskId: string, workerId: string): Promise<FactoryTask> {
  return withTransaction(async (client) => {
    const { rows } = await client.query(
      "SELECT * FROM tasks WHERE id = $1 FOR UPDATE",
      [taskId],
    );
    if (!rows[0]) throw new Error(`task not found: ${taskId}`);
    const current = rowToTask(rows[0]);
    if (current.status !== "proposed") {
      throw new Error(`task ${taskId} not claimable (status=${current.status})`);
    }
    const { rows: updated } = await client.query(
      `UPDATE tasks SET status = 'claimed', assignee_agent = $2, claimed_at = now(), updated_at = now()
       WHERE id = $1 RETURNING *`,
      [taskId, workerId],
    );
    return rowToTask(updated[0]);
  });
}

export async function claimNextProposed(workerId: string): Promise<FactoryTask | null> {
  return withTransaction(async (client) => {
    const { rows } = await client.query(
      `SELECT * FROM tasks WHERE status = 'proposed' ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED`,
    );
    if (!rows[0]) return null;
    const taskId = String(rows[0].id);
    const { rows: updated } = await client.query(
      `UPDATE tasks SET status = 'claimed', assignee_agent = $2, claimed_at = now(), updated_at = now()
       WHERE id = $1 RETURNING *`,
      [taskId, workerId],
    );
    return rowToTask(updated[0]);
  });
}

export async function nextTaskId(): Promise<string> {
  const { rows } = await query(
    `SELECT id FROM tasks WHERE id ~ '^TASK-[0-9]+$' ORDER BY id DESC LIMIT 1`,
  );
  let max = 0;
  if (rows[0]?.id) {
    const m = String(rows[0].id).match(/^TASK-(\d+)$/);
    if (m) max = parseInt(m[1], 10);
  }
  return `TASK-${String(max + 1).padStart(3, "0")}`;
}

export async function saveSlackThread(
  channelId: string,
  threadTs: string,
  taskId: string,
  prUrl?: string | null,
): Promise<void> {
  await query(
    `INSERT INTO slack_threads (channel_id, thread_ts, task_id, pr_url)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (channel_id, thread_ts) DO UPDATE SET task_id = EXCLUDED.task_id, pr_url = COALESCE(EXCLUDED.pr_url, slack_threads.pr_url)`,
    [channelId, threadTs, taskId, prUrl ?? null],
  );
}

export async function getSlackThread(
  channelId: string,
  threadTs: string,
): Promise<{ task_id: string; pr_url: string | null } | null> {
  const { rows } = await query(
    "SELECT task_id, pr_url FROM slack_threads WHERE channel_id = $1 AND thread_ts = $2",
    [channelId, threadTs],
  );
  if (!rows[0]) return null;
  return {
    task_id: String(rows[0].task_id),
    pr_url: rows[0].pr_url ? String(rows[0].pr_url) : null,
  };
}

export async function updateSlackThreadPr(
  channelId: string,
  threadTs: string,
  prUrl: string,
): Promise<void> {
  await query(
    "UPDATE slack_threads SET pr_url = $3 WHERE channel_id = $1 AND thread_ts = $2",
    [channelId, threadTs, prUrl],
  );
}
