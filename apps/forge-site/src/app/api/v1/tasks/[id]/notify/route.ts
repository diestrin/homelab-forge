import {
  badRequest,
  isDbConfigured,
  notFound,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { enqueueNotify } from "@/lib/control-plane/jobs";
import { getTask } from "@/lib/control-plane/tasks";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type RouteProps = { params: Promise<{ id: string }> };

/**
 * Failure/progress reporting path (TASK-011): agents and workers POST here;
 * the control plane's notify consumer posts to the bound Slack thread.
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
  const message = typeof body.body === "string" ? body.body.trim() : "";
  if (!message) return badRequest("body is required");

  const jobId = await enqueueNotify(id, { body: message });
  return NextResponse.json({ job_id: jobId }, { status: 202 });
}
