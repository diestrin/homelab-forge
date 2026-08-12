import {
  badRequest,
  isDbConfigured,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { claimWork } from "@/lib/control-plane/actions";
import { claimJob } from "@/lib/control-plane/jobs";
import type { JobKind } from "@/lib/control-plane/types";
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

  const workerId =
    typeof body.worker_id === "string" ? body.worker_id : "worker-anonymous";
  const taskId = typeof body.task_id === "string" ? body.task_id : undefined;
  const useQueue = body.via_queue === true;

  try {
    if (useQueue) {
      const kinds = (Array.isArray(body.kinds)
        ? body.kinds.filter((k): k is JobKind => typeof k === "string")
        : ["implement"]) as JobKind[];
      const job = await claimJob(kinds.length ? kinds : ["implement"], workerId);
      if (!job) {
        return NextResponse.json({ claimed: false, task: null, job: null });
      }
      const work = await claimWork(workerId, job.payload.taskId);
      return NextResponse.json({
        claimed: Boolean(work),
        task: work?.task ?? null,
        job,
        source: "pg-boss",
      });
    }

    const work = await claimWork(workerId, taskId);
    if (!work) {
      return NextResponse.json({ claimed: false, task: null });
    }
    return NextResponse.json({ claimed: true, task: work.task, source: work.source });
  } catch (err) {
    const message = err instanceof Error ? err.message : "claim failed";
    return badRequest(message);
  }
}
