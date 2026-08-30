import { appendMessage } from "./messages";
import { runControlAction } from "./actions";
import { enqueueNotify, enqueuePlan } from "./jobs";
import {
  createTask,
  getSlackThread,
  getTask,
  nextTaskId,
  saveSlackThread,
} from "./tasks";
import type { FactoryTask } from "./types";

/**
 * Slack intake (TASK-011): the host Socket Mode client only records intent
 * here. The control plane creates/updates tasks, pins the branch once, and
 * enqueues plan/implement/notify jobs. It never runs the LLM in-process.
 */

const APPROVE_RE = /^\s*(approve|lgtm|\/forge\s+approve)\s*$/i;
const HUMAN_ONLY_RE =
  /\b(ssh|ufw|vault\s+unseal|host-watch|force-?push|kubectl\s+apply)\b/i;

export function slugify(text: string, maxLen = 40): string {
  const s = text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (s.slice(0, maxLen) || "request").replace(/^-+|-+$/g, "");
}

export type IntakeInput = {
  kind: "plan" | "thread_reply";
  channel_id: string;
  thread_ts: string;
  text: string;
  author?: string;
};

export type IntakeResult = {
  action: "plan" | "plan-update" | "approve" | "stored";
  task: FactoryTask;
  job_id?: string | null;
  human_only?: boolean;
};

async function handleNewPlan(input: IntakeInput): Promise<IntakeResult> {
  const id = await nextTaskId();
  const text = input.text.trim();
  const humanOnly = HUMAN_ONLY_RE.test(text);
  // Branch is pinned once at intake; planner and worker must never rewrite it
  // (TASK-011 regression: PRs #16→#19, #18→#20).
  const branch = `factory/${id.toLowerCase()}-${slugify(text)}`;

  const task = await createTask({
    id,
    title: text.slice(0, 72),
    goal: text,
    acceptance_criteria: [
      "Plan refined via Slack thread and approved before worker claim",
    ],
    status: "planning",
    branch,
    risk_level: humanOnly ? "high" : "medium",
    notes: humanOnly
      ? "HUMAN-ONLY intent detected; do not approve without operator review."
      : "Created from Slack intake; plan job drafts the full task.",
  });
  await saveSlackThread(input.channel_id, input.thread_ts, id);
  await appendMessage({
    task_id: id,
    source: "slack",
    author: input.author ?? "operator",
    body: text,
    metadata: { intake: "plan" },
  });
  const jobId = await enqueuePlan(id, {
    mode: "create",
    request: text,
    channel_id: input.channel_id,
    thread_ts: input.thread_ts,
  });
  return { action: "plan", task, job_id: jobId, human_only: humanOnly };
}

async function handleThreadReply(input: IntakeInput): Promise<IntakeResult> {
  const binding = await getSlackThread(input.channel_id, input.thread_ts);
  if (!binding) throw new Error("no task bound to this thread");
  const task = await getTask(binding.task_id);
  if (!task) throw new Error(`task not found: ${binding.task_id}`);
  const text = input.text.trim();

  if (APPROVE_RE.test(text)) {
    const { task: updated } = await runControlAction(task.id, "approve", "slack");
    const jobId = await enqueueNotify(task.id, {
      body:
        `\`${task.id}\` → *proposed* (worker-claimable).\n` +
        `PR: ${binding.pr_url ?? "(see plan PR on GitHub)"}\n` +
        "Worker will implement via Cursor SDK on the pinned branch and update the same PR.",
    });
    return { action: "approve", task: updated ?? task, job_id: jobId };
  }

  await appendMessage({
    task_id: task.id,
    source: "slack",
    author: input.author ?? "operator",
    body: text,
    metadata: { intake: "thread_reply", task_status: task.status },
  });

  if (task.status === "planning") {
    const jobId = await enqueuePlan(task.id, {
      mode: "update",
      feedback: text,
      channel_id: input.channel_id,
      thread_ts: input.thread_ts,
    });
    return { action: "plan-update", task, job_id: jobId };
  }

  // Post-approve replies are stored on the task; they never spawn a fresh
  // plan-PR cycle or a host planner run (TASK-011).
  const jobId = await enqueueNotify(task.id, {
    body:
      `Noted on \`${task.id}\` (status: ${task.status}) — feedback stored on the task.\n` +
      "No new plan PR is opened after approve; CI is watched automatically. " +
      "Use `/forge plan …` for new work.",
  });
  return { action: "stored", task, job_id: jobId };
}

export async function handleSlackIntake(input: IntakeInput): Promise<IntakeResult> {
  if (input.kind === "plan") return handleNewPlan(input);
  return handleThreadReply(input);
}
