import { query } from "@/lib/db/pool";
import { rowToRun, type AgentRun, type RunEvent, type RunStatus } from "./types";

export type CreateRunInput = {
  task_id: string;
  kind: string;
  worker_id?: string | null;
  model?: string | null;
  branch?: string | null;
  job_id?: string | null;
};

export type UpdateRunInput = Partial<{
  status: RunStatus;
  agent_id: string | null;
  sdk_run_id: string | null;
  summary: string | null;
  error: string | null;
}>;

/** Max events kept per run; oldest are dropped beyond this to bound row size. */
const MAX_TRANSCRIPT_EVENTS = 2000;

export async function createRun(input: CreateRunInput): Promise<AgentRun> {
  const { rows } = await query(
    `INSERT INTO agent_runs (task_id, kind, worker_id, model, branch, job_id)
     VALUES ($1, $2, $3, $4, $5, $6)
     RETURNING *`,
    [
      input.task_id,
      input.kind,
      input.worker_id ?? null,
      input.model ?? null,
      input.branch ?? null,
      input.job_id ?? null,
    ],
  );
  return rowToRun(rows[0]);
}

export async function getRun(id: string): Promise<AgentRun | null> {
  const { rows } = await query("SELECT * FROM agent_runs WHERE id = $1", [id]);
  if (!rows[0]) return null;
  return rowToRun(rows[0]);
}

/** Runs for a task without full transcripts (event_count instead). */
export async function listRuns(taskId: string): Promise<AgentRun[]> {
  const { rows } = await query(
    `SELECT id, task_id, kind, status, worker_id, model, branch, agent_id,
            sdk_run_id, job_id, summary, error,
            jsonb_array_length(transcript) AS event_count,
            started_at, finished_at, created_at, updated_at
     FROM agent_runs WHERE task_id = $1 ORDER BY started_at DESC`,
    [taskId],
  );
  return rows.map((r) => rowToRun(r));
}

export async function appendRunEvents(id: string, events: RunEvent[]): Promise<number> {
  if (events.length === 0) return 0;
  const { rows } = await query(
    `UPDATE agent_runs
     SET transcript = (
       SELECT COALESCE(jsonb_agg(e ORDER BY ord), '[]'::jsonb)
       FROM (
         SELECT e, ord
         FROM jsonb_array_elements(transcript || $2::jsonb) WITH ORDINALITY AS t(e, ord)
         ORDER BY ord DESC
         LIMIT $3
       ) tail
     ),
     updated_at = now()
     WHERE id = $1
     RETURNING jsonb_array_length(transcript) AS event_count`,
    [id, JSON.stringify(events), MAX_TRANSCRIPT_EVENTS],
  );
  if (!rows[0]) throw new Error(`run not found: ${id}`);
  return Number(rows[0].event_count);
}

export async function updateRun(id: string, patch: UpdateRunInput): Promise<AgentRun> {
  const fields: string[] = [];
  const values: unknown[] = [];
  let i = 1;
  const setField = (col: string, val: unknown) => {
    fields.push(`${col} = $${i++}`);
    values.push(val);
  };

  if (patch.status !== undefined) {
    setField("status", patch.status);
    if (patch.status !== "running") {
      fields.push("finished_at = COALESCE(finished_at, now())");
    }
  }
  if (patch.agent_id !== undefined) setField("agent_id", patch.agent_id);
  if (patch.sdk_run_id !== undefined) setField("sdk_run_id", patch.sdk_run_id);
  if (patch.summary !== undefined) setField("summary", patch.summary);
  if (patch.error !== undefined) setField("error", patch.error);
  fields.push("updated_at = now()");
  values.push(id);

  const { rows } = await query(
    `UPDATE agent_runs SET ${fields.join(", ")} WHERE id = $${i} RETURNING *`,
    values,
  );
  if (!rows[0]) throw new Error(`run not found: ${id}`);
  return rowToRun(rows[0]);
}
