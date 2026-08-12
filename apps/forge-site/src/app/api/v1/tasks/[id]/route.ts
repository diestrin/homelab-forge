import {
  badRequest,
  isDbConfigured,
  notFound,
  optionalApiAuthForRead,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { getTask, updateTask, addArtifact } from "@/lib/control-plane/tasks";
import type { Artifact, TaskStatus } from "@/lib/control-plane/types";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function GET(_request: Request, { params }: Params) {
  const authErr = await optionalApiAuthForRead();
  if (authErr) return authErr;
  const { id } = await params;
  if (!isDbConfigured()) {
    return NextResponse.json({ task: null, db: false });
  }
  try {
    const task = await getTask(id);
    if (!task) return notFound(`task not found: ${id}`);
    return NextResponse.json({ task, db: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "failed to get task";
    return serverError(message);
  }
}

export async function PATCH(request: Request, { params }: Params) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  const { id } = await params;
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
    const patch: Parameters<typeof updateTask>[1] = {};
    if (typeof body.title === "string") patch.title = body.title;
    if (typeof body.goal === "string") patch.goal = body.goal;
    if (Array.isArray(body.acceptance_criteria)) {
      patch.acceptance_criteria = body.acceptance_criteria.filter(
        (x): x is string => typeof x === "string",
      );
    }
    if (typeof body.status === "string") patch.status = body.status as TaskStatus;
    if (body.assignee_agent === null || typeof body.assignee_agent === "string") {
      patch.assignee_agent = body.assignee_agent as string | null;
    }
    if (typeof body.branch === "string" || body.branch === null) {
      patch.branch = body.branch as string | null;
    }
    if (typeof body.notes === "string" || body.notes === null) {
      patch.notes = body.notes as string | null;
    }
    if (typeof body.github_project_item_id === "string" || body.github_project_item_id === null) {
      patch.github_project_item_id = body.github_project_item_id as string | null;
    }

    if (body.artifact && typeof body.artifact === "object") {
      const art = body.artifact as Artifact;
      if (art.kind && art.path) {
        const task = await addArtifact(id, art);
        return NextResponse.json({ task });
      }
    }

    const task = await updateTask(id, patch);
    return NextResponse.json({ task });
  } catch (err) {
    const message = err instanceof Error ? err.message : "failed to update task";
    if (message.includes("not found")) return notFound(message);
    if (message.includes("illegal transition")) return badRequest(message);
    return serverError(message);
  }
}
