import {
  badRequest,
  isDbConfigured,
  notFound,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { enqueueJob } from "@/lib/control-plane/jobs";
import { getTask } from "@/lib/control-plane/tasks";
import { JOB_KINDS, type JobKind } from "@/lib/control-plane/types";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type RouteProps = { params: Promise<{ id: string }> };

/**
 * Enqueue a job for a task (TASK-011): used by the CI watch loop to dispatch
 * fix runs and follow-up watches. The control plane owns the queue; hosts
 * never talk to pg-boss directly.
 */
export async function POST(request: Request, { params }: RouteProps) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }
  const { id } = await params;
  const task = await getTask(id);
  if (!task) return notFound(`task not found: ${id}`);

  let body: Record<string, unknown> = {};
  try {
    const text = await request.text();
    if (text) body = JSON.parse(text) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  const kind = typeof body.kind === "string" ? body.kind : "";
  if (!JOB_KINDS.includes(kind as JobKind)) {
    return badRequest(`kind must be one of ${JOB_KINDS.join(", ")}`);
  }
  const meta =
    body.meta && typeof body.meta === "object"
      ? (body.meta as Record<string, unknown>)
      : undefined;

  const jobId = await enqueueJob(kind as JobKind, { taskId: id, meta });
  return NextResponse.json({ job_id: jobId, kind }, { status: 202 });
}
