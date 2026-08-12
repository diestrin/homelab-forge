import { query } from "@/lib/db/pool";
import { rowToMessage, type TaskMessage } from "./types";

export async function listMessages(taskId: string): Promise<TaskMessage[]> {
  const { rows } = await query(
    "SELECT * FROM task_messages WHERE task_id = $1 ORDER BY created_at ASC",
    [taskId],
  );
  return rows.map((r) => rowToMessage(r));
}

export async function appendMessage(input: {
  task_id: string;
  source: string;
  author?: string | null;
  body: string;
  metadata?: Record<string, unknown>;
}): Promise<TaskMessage> {
  const { rows } = await query(
    `INSERT INTO task_messages (task_id, source, author, body, metadata)
     VALUES ($1, $2, $3, $4, $5::jsonb)
     RETURNING *`,
    [
      input.task_id,
      input.source,
      input.author ?? null,
      input.body,
      JSON.stringify(input.metadata ?? {}),
    ],
  );
  return rowToMessage(rows[0]);
}
