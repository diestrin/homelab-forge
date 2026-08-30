import {
  badRequest,
  isDbConfigured,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { createRun } from "@/lib/control-plane/runs";
import { getTask } from "@/lib/control-plane/tasks";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }

  let body: Record<string, unknown> = {};
  try {
    const text = await request.text();
    if (text) body = JSON.parse(text) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  const taskId = typeof body.task_id === "string" ? body.task_id : "";
  const kind = typeof body.kind === "string" ? body.kind : "";
  if (!taskId || !kind) {
    return badRequest("task_id and kind are required");
  }
  const task = await getTask(taskId);
  if (!task) return badRequest(`task not found: ${taskId}`);

  try {
    const run = await createRun({
      task_id: taskId,
      kind,
      worker_id: typeof body.worker_id === "string" ? body.worker_id : null,
      model: typeof body.model === "string" ? body.model : null,
      branch: typeof body.branch === "string" ? body.branch : task.branch,
      job_id: typeof body.job_id === "string" ? body.job_id : null,
    });
    return NextResponse.json({ run }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "create run failed";
    return badRequest(message);
  }
}
