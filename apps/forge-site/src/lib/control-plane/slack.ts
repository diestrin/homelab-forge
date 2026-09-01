import { query } from "@/lib/db/pool";
import { appendMessage } from "./messages";

/**
 * Outbound Slack for the control plane (ADR-010 notify queue, TASK-011).
 * Token comes from Vault secret/forge/agents/slack via ExternalSecret — never git.
 * Socket Mode intake stays on the host; this is plain chat.postMessage.
 */
export function isSlackConfigured(): boolean {
  return Boolean(process.env.SLACK_BOT_TOKEN?.trim());
}

async function postMessage(
  channel: string,
  text: string,
  threadTs?: string,
): Promise<{ ok: boolean; error?: string }> {
  const token = process.env.SLACK_BOT_TOKEN?.trim();
  if (!token) return { ok: false, error: "SLACK_BOT_TOKEN not configured" };
  const res = await fetch("https://slack.com/api/chat.postMessage", {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      channel,
      text,
      ...(threadTs ? { thread_ts: threadTs } : {}),
    }),
  });
  const data = (await res.json()) as { ok: boolean; error?: string };
  return { ok: data.ok, error: data.error };
}

async function threadForTask(
  taskId: string,
): Promise<{ channel_id: string; thread_ts: string } | null> {
  const { rows } = await query(
    `SELECT channel_id, thread_ts FROM slack_threads
     WHERE task_id = $1 ORDER BY thread_ts DESC LIMIT 1`,
    [taskId],
  );
  if (!rows[0]) return null;
  return {
    channel_id: String(rows[0].channel_id),
    thread_ts: String(rows[0].thread_ts),
  };
}

/**
 * Post `body` to the Slack thread bound to a task and persist it as a task
 * message. This is the only agent-progress path back to Slack (TASK-011).
 */
export async function notifyTaskThread(
  taskId: string,
  body: string,
  author = "control-plane",
): Promise<{ posted: boolean; reason?: string }> {
  await appendMessage({
    task_id: taskId,
    source: "notify",
    author,
    body,
  });
  const thread = await threadForTask(taskId);
  if (!thread) return { posted: false, reason: "no slack thread bound to task" };
  const res = await postMessage(thread.channel_id, body, thread.thread_ts);
  if (!res.ok) return { posted: false, reason: res.error ?? "slack error" };
  return { posted: true };
}
