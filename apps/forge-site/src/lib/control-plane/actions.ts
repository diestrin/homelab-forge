import { appendMessage } from "./messages";
import {
  claimNextProposed,
  claimTask,
  getTask,
  updateTask,
} from "./tasks";
import { enqueueImplement, enqueueSyncProjects } from "./jobs";
import type { ControlAction } from "./types";

export async function runControlAction(
  taskId: string,
  action: ControlAction,
  actor?: string,
): Promise<{ task: Awaited<ReturnType<typeof getTask>>; jobId?: string | null }> {
  const task = await getTask(taskId);
  if (!task) throw new Error(`task not found: ${taskId}`);

  switch (action) {
    case "approve": {
      if (task.status !== "planning") {
        throw new Error(`approve requires planning status (current=${task.status})`);
      }
      const updated = await updateTask(taskId, { status: "proposed" });
      const jobId = await enqueueImplement(taskId);
      await appendMessage({
        task_id: taskId,
        source: "system",
        author: actor ?? null,
        body: "Task approved → proposed; implement job enqueued.",
        metadata: { action, jobId },
      });
      await enqueueSyncProjects(taskId);
      return { task: updated, jobId };
    }
    case "cancel": {
      const updated = await updateTask(taskId, { status: "failed" });
      await appendMessage({
        task_id: taskId,
        source: "system",
        author: actor ?? null,
        body: "Task cancelled → failed.",
        metadata: { action },
      });
      return { task: updated };
    }
    case "retry": {
      if (task.status !== "failed") {
        throw new Error(`retry requires failed status (current=${task.status})`);
      }
      const updated = await updateTask(taskId, { status: "proposed", assignee_agent: null });
      const jobId = await enqueueImplement(taskId);
      await appendMessage({
        task_id: taskId,
        source: "system",
        author: actor ?? null,
        body: "Task retried → proposed; implement job enqueued.",
        metadata: { action, jobId },
      });
      return { task: updated, jobId };
    }
    default:
      throw new Error(`unknown action: ${action}`);
  }
}

export async function claimWork(
  workerId: string,
  taskId?: string,
): Promise<{ task: NonNullable<Awaited<ReturnType<typeof getTask>>>; source: string } | null> {
  if (taskId) {
    const task = await claimTask(taskId, workerId);
    return { task, source: "direct" };
  }
  const task = await claimNextProposed(workerId);
  if (task) return { task, source: "queue" };
  return null;
}
