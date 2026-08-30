import {
  badRequest,
  isDbConfigured,
  notFound,
  optionalApiAuthForRead,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { getRun, updateRun, type UpdateRunInput } from "@/lib/control-plane/runs";
import { RUN_STATUSES, type RunStatus } from "@/lib/control-plane/types";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type RouteProps = { params: Promise<{ id: string }> };

export async function GET(_request: Request, { params }: RouteProps) {
  const authErr = await optionalApiAuthForRead();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }
  const { id } = await params;
  const run = await getRun(id);
  if (!run) return notFound(`run not found: ${id}`);
  return NextResponse.json({ run });
}

export async function PATCH(request: Request, { params }: RouteProps) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }
  const { id } = await params;

  let body: Record<string, unknown> = {};
  try {
    const text = await request.text();
    if (text) body = JSON.parse(text) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  const patch: UpdateRunInput = {};
  if (body.status !== undefined) {
    if (
      typeof body.status !== "string" ||
      !RUN_STATUSES.includes(body.status as RunStatus)
    ) {
      return badRequest(`status must be one of ${RUN_STATUSES.join(", ")}`);
    }
    patch.status = body.status as RunStatus;
  }
  if (body.agent_id !== undefined) patch.agent_id = body.agent_id as string | null;
  if (body.sdk_run_id !== undefined) patch.sdk_run_id = body.sdk_run_id as string | null;
  if (body.summary !== undefined) patch.summary = body.summary as string | null;
  if (body.error !== undefined) patch.error = body.error as string | null;

  try {
    const run = await updateRun(id, patch);
    return NextResponse.json({ run });
  } catch (err) {
    const message = err instanceof Error ? err.message : "update run failed";
    return badRequest(message);
  }
}
