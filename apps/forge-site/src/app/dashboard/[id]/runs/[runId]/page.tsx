import Link from "next/link";
import { notFound } from "next/navigation";
import { loadRunFromDb, loadTaskFromDb } from "@/lib/tasks";
import type { RunEvent } from "@/lib/control-plane/types";

export const dynamic = "force-dynamic";

type PageProps = { params: Promise<{ id: string; runId: string }> };

function eventBadgeClass(type: string): string {
  switch (type) {
    case "assistant":
      return "bg-amber-500/15 text-amber-300 ring-amber-500/30";
    case "tool_call":
      return "bg-sky-500/15 text-sky-300 ring-sky-500/30";
    case "tool_result":
      return "bg-violet-500/15 text-violet-300 ring-violet-500/30";
    case "error":
      return "bg-red-500/15 text-red-300 ring-red-500/30";
    default:
      return "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30";
  }
}

function EventDetail({ event }: { event: RunEvent }) {
  const { type, ts, text, tool, ...rest } = event;
  void type;
  void ts;
  const hasRest = Object.keys(rest).length > 0;
  return (
    <>
      {typeof tool === "string" && tool && (
        <p className="font-mono text-xs text-sky-300">{tool}</p>
      )}
      {typeof text === "string" && text && (
        <p className="whitespace-pre-wrap text-sm text-zinc-200">{text}</p>
      )}
      {hasRest && (
        <details className="text-xs text-zinc-500">
          <summary className="cursor-pointer select-none hover:text-zinc-300">
            details
          </summary>
          <pre className="mt-2 overflow-x-auto rounded bg-zinc-950/60 p-3 text-zinc-400">
            {JSON.stringify(rest, null, 2)}
          </pre>
        </details>
      )}
    </>
  );
}

export default async function RunTranscriptPage({ params }: PageProps) {
  const { id, runId } = await params;
  const [task, run] = await Promise.all([loadTaskFromDb(id), loadRunFromDb(runId)]);
  if (!task || !run || run.task_id !== task.id) notFound();

  const transcript = run.transcript ?? [];

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <p className="mb-6">
        <Link
          href={`/dashboard/${task.id}`}
          className="text-sm text-zinc-400 hover:text-zinc-200"
        >
          ← {task.id}
        </Link>
      </p>

      <div className="mb-8">
        <p className="mb-1 font-mono text-sm text-amber-400/90">
          {task.id} · {run.kind} run
        </p>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-50">
          Agent transcript
        </h1>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-zinc-500">Status</dt>
            <dd className="text-zinc-200">{run.status}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Started</dt>
            <dd className="text-zinc-200">{new Date(run.started_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Model</dt>
            <dd className="text-zinc-200">{run.model ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Branch</dt>
            <dd className="font-mono text-zinc-200">{run.branch ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">SDK run</dt>
            <dd className="font-mono text-xs text-zinc-200">
              {run.sdk_run_id ?? "—"}
            </dd>
          </div>
          <div>
            <dt className="text-zinc-500">Worker</dt>
            <dd className="text-zinc-200">{run.worker_id ?? "—"}</dd>
          </div>
        </dl>
        {run.error && (
          <p className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
            {run.error}
          </p>
        )}
        {run.summary && (
          <p className="mt-4 whitespace-pre-wrap rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-sm text-zinc-300">
            {run.summary}
          </p>
        )}
      </div>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Conversation ({transcript.length} events, redacted)
        </h2>
        {transcript.length === 0 ? (
          <p className="text-sm text-zinc-500">No transcript events recorded.</p>
        ) : (
          <ol className="space-y-4">
            {transcript.map((event, i) => {
              const type = typeof event.type === "string" ? event.type : "event";
              const ts = typeof event.ts === "string" ? event.ts : null;
              return (
                <li key={i} className="border-l-2 border-zinc-700 pl-4">
                  <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 font-medium ring-1 ring-inset ${eventBadgeClass(type)}`}
                    >
                      {type}
                    </span>
                    {ts && (
                      <span className="text-zinc-500">
                        {new Date(ts).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                  <EventDetail event={event} />
                </li>
              );
            })}
          </ol>
        )}
      </section>
    </main>
  );
}
