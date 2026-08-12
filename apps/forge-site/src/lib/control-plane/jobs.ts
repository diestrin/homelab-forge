import PgBoss from "pg-boss";
import type { JobKind } from "./types";

let boss: PgBoss | null = null;
let started = false;

export type JobPayload = {
  taskId: string;
  kind: JobKind;
  workerId?: string;
  meta?: Record<string, unknown>;
};

async function getBoss(): Promise<PgBoss | null> {
  const url = process.env.DATABASE_URL?.trim();
  if (!url) return null;
  if (!boss) {
    boss = new PgBoss({ connectionString: url });
  }
  if (!started) {
    await boss.start();
    started = true;
    for (const queue of ["plan", "implement", "notify", "sync-projects"] as JobKind[]) {
      await boss.createQueue(queue);
    }
  }
  return boss;
}

export async function enqueueJob(
  kind: JobKind,
  payload: Omit<JobPayload, "kind">,
): Promise<string | null> {
  const b = await getBoss();
  if (!b) return null;
  const id = await b.send(kind, { ...payload, kind });
  return id ?? null;
}

export async function claimJob(
  kinds: JobKind[],
  workerId: string,
): Promise<{ id: string; kind: JobKind; payload: JobPayload } | null> {
  const b = await getBoss();
  if (!b) return null;
  for (const kind of kinds) {
    const jobs = await b.fetch<{ taskId: string; kind: JobKind; meta?: Record<string, unknown> }>(
      kind,
      { batchSize: 1 },
    );
    if (jobs.length === 0) continue;
    const job = jobs[0];
    await b.complete(kind, job.id);
    return {
      id: job.id,
      kind,
      payload: {
        taskId: job.data.taskId,
        kind,
        workerId,
        meta: job.data.meta,
      },
    };
  }
  return null;
}

export async function enqueueImplement(taskId: string): Promise<string | null> {
  return enqueueJob("implement", { taskId });
}

export async function enqueuePlan(taskId: string, meta?: Record<string, unknown>): Promise<string | null> {
  return enqueueJob("plan", { taskId, meta });
}

export async function enqueueNotify(
  taskId: string,
  meta?: Record<string, unknown>,
): Promise<string | null> {
  return enqueueJob("notify", { taskId, meta });
}

export async function enqueueSyncProjects(taskId?: string): Promise<string | null> {
  return enqueueJob("sync-projects", { taskId: taskId ?? "all" });
}
