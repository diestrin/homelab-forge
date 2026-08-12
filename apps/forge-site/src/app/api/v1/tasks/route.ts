import {
  badRequest,
  isDbConfigured,
  optionalApiAuthForRead,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { createTask, listTasks, nextTaskId } from "@/lib/control-plane/tasks";
import { appendMessage } from "@/lib/control-plane/messages";
import { enqueuePlan } from "@/lib/control-plane/jobs";
import type { TaskStatus } from "@/lib/control-plane/types";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const authErr = await optionalApiAuthForRead();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return NextResponse.json({ tasks: [], db: false });
  }
  try {
    const tasks = await listTasks();
    return NextResponse.json({ tasks, db: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "failed to list tasks";
    return serverError(message);
  }
}

export async function POST(request: Request) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  try {
    let id = typeof body.id === "string" ? body.id : "";
    if (!id) id = await nextTaskId();

    const title = typeof body.title === "string" ? body.title : "";
    const goal = typeof body.goal === "string" ? body.goal : "";
    const ac = Array.isArray(body.acceptance_criteria)
      ? body.acceptance_criteria.filter((x): x is string => typeof x === "string")
      : [];

    if (!title || !goal || ac.length === 0) {
      return badRequest("title, goal, and acceptance_criteria[] required");
    }

    const status = (typeof body.status === "string" ? body.status : "planning") as TaskStatus;

    const task = await createTask({
      id,
      title,
      goal,
      acceptance_criteria: ac,
      sandbox_profile:
        typeof body.sandbox_profile === "string" ? body.sandbox_profile : undefined,
      repo_path: typeof body.repo_path === "string" ? body.repo_path : undefined,
      status,
      risk_level: typeof body.risk_level === "string" ? body.risk_level : undefined,
      branch: typeof body.branch === "string" ? body.branch : undefined,
      worker_hook: typeof body.worker_hook === "string" ? body.worker_hook : undefined,
      notes: typeof body.notes === "string" ? body.notes : undefined,
      budget_minutes:
        typeof body.budget_minutes === "number" ? body.budget_minutes : undefined,
    });

    const initialMessage =
      typeof body.initial_message === "string" ? body.initial_message : null;
    if (initialMessage) {
      await appendMessage({
        task_id: task.id,
        source: typeof body.message_source === "string" ? body.message_source : "system",
        author: typeof body.author === "string" ? body.author : null,
        body: initialMessage,
      });
    }

    if (body.enqueue_plan === true) {
      await enqueuePlan(task.id, { request: goal });
    }

    return NextResponse.json({ task }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "failed to create task";
    return serverError(message);
  }
}
