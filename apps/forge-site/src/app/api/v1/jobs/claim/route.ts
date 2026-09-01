import {
  badRequest,
  isDbConfigured,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { claimWork } from "@/lib/control-plane/actions";
import { claimJob } from "@/lib/control-plane/jobs";
import { getTask } from "@/lib/control-plane/tasks";
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
      if (job) {
        // Only implement jobs on proposed tasks transition task status here.
        // Plan/watch jobs (and fix runs on review tasks) leave status alone —
        // the job runner owns any further transitions (TASK-011).
        const current = await getTask(job.payload.taskId);
        if (job.kind === "implement" && current?.status === "proposed") {
          const work = await claimWork(workerId, job.payload.taskId);
          return NextResponse.json({
            claimed: Boolean(work),
            task: work?.task ?? null,
            job,
            source: "pg-boss",
          });
        }
        return NextResponse.json({
          claimed: Boolean(current),
          task: current,
          job,
          source: "pg-boss",
        });
      }
      // Queue empty or job already consumed — still claim a proposed task,
      // but only when the caller asked for implement work.
      if (!kinds.includes("implement")) {
        return NextResponse.json({ claimed: false, task: null, job: null });
      }
      const work = await claimWork(workerId, taskId);
      if (!work) {
        return NextResponse.json({ claimed: false, task: null, job: null });
      }
      return NextResponse.json({
        claimed: true,
        task: work.task,
        job: null,
        source: work.source,
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
