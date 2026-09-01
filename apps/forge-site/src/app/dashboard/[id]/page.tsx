import Link from "next/link";
import { notFound } from "next/navigation";
import { loadMessagesFromDb, loadRunsFromDb, loadTaskFromDb } from "@/lib/tasks";

export const dynamic = "force-dynamic";

type PageProps = { params: Promise<{ id: string }> };

function statusBadgeClass(status: string): string {
  switch (status) {
    case "done":
      return "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30";
    case "failed":
      return "bg-red-500/15 text-red-300 ring-red-500/30";
    case "in_progress":
    case "claimed":
      return "bg-sky-500/15 text-sky-300 ring-sky-500/30";
    case "review":
      return "bg-violet-500/15 text-violet-300 ring-violet-500/30";
    case "proposed":
      return "bg-amber-500/15 text-amber-300 ring-amber-500/30";
    case "planning":
      return "bg-orange-500/15 text-orange-300 ring-orange-500/30";
    default:
      return "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30";
  }
}

function runStatusClass(status: string): string {
  switch (status) {
    case "finished":
      return "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30";
    case "error":
      return "bg-red-500/15 text-red-300 ring-red-500/30";
    case "running":
      return "bg-sky-500/15 text-sky-300 ring-sky-500/30";
    case "cancelled":
      return "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30";
    default:
      return "bg-zinc-500/15 text-zinc-300 ring-zinc-500/30";
  }
}

export default async function TaskDetailPage({ params }: PageProps) {
  const { id } = await params;
  const task = await loadTaskFromDb(id);
  if (!task) notFound();

  const [messages, runs] = await Promise.all([
    loadMessagesFromDb(id),
    loadRunsFromDb(id),
  ]);

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <p className="mb-6">
        <Link href="/dashboard" className="text-sm text-zinc-400 hover:text-zinc-200">
          ← All tasks
        </Link>
      </p>

      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-1 font-mono text-sm text-amber-400/90">{task.id}</p>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-50">{task.title}</h1>
        </div>
        <span
          className={`inline-flex rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset ${statusBadgeClass(task.status)}`}
        >
          {task.status}
        </span>
      </div>

      <section className="mb-8 space-y-4 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Goal
          </h2>
          <p className="whitespace-pre-wrap text-zinc-200">{task.goal}</p>
        </div>
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Acceptance criteria
          </h2>
          <ul className="list-inside list-disc space-y-1 text-zinc-300">
            {task.acceptance_criteria.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-zinc-500">Assignee</dt>
            <dd className="text-zinc-200">{task.assignee_agent ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Branch</dt>
            <dd className="font-mono text-zinc-200">{task.branch ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Sandbox</dt>
            <dd className="text-zinc-200">{task.sandbox_profile}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Risk</dt>
            <dd className="text-zinc-200">{task.risk_level}</dd>
          </div>
        </dl>
      </section>

      {task.artifacts.length > 0 && (
        <section className="mb-8 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Artifacts
          </h2>
          <ul className="space-y-2 text-sm">
            {task.artifacts.map((art, i) => (
              <li key={`${art.kind}-${art.path}-${i}`} className="text-zinc-300">
                <span className="font-mono text-amber-400/80">{art.kind}</span>{" "}
                {art.url ? (
                  <a href={art.url} className="text-sky-400 hover:underline">
                    {art.path}
                  </a>
                ) : (
                  art.path
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mb-8 rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Agent runs
        </h2>
        {runs.length === 0 ? (
          <p className="text-sm text-zinc-500">No agent runs recorded yet.</p>
        ) : (
          <ul className="space-y-3">
            {runs.map((run) => (
              <li
                key={run.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-sm"
              >
                <span
                  className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${runStatusClass(run.status)}`}
                >
                  {run.status}
                </span>
                <span className="font-mono text-amber-400/80">{run.kind}</span>
                <span className="text-zinc-500">
                  {new Date(run.started_at).toLocaleString()}
                </span>
                {run.model && <span className="text-zinc-500">· {run.model}</span>}
                <span className="text-zinc-500">
                  · {run.event_count ?? 0} events
                </span>
                <Link
                  href={`/dashboard/${task.id}/runs/${run.id}`}
                  className="ml-auto text-sky-400 hover:underline"
                >
                  Transcript →
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">
          Message history
        </h2>
        {messages.length === 0 ? (
          <p className="text-sm text-zinc-500">No messages yet.</p>
        ) : (
          <ul className="space-y-4">
            {messages.map((msg) => (
              <li key={msg.id} className="border-l-2 border-zinc-700 pl-4">
                <div className="mb-1 flex flex-wrap gap-2 text-xs text-zinc-500">
                  <span className="font-medium text-zinc-400">{msg.source}</span>
                  {msg.author && <span>· {msg.author}</span>}
                  <span>· {new Date(msg.created_at).toLocaleString()}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-zinc-200">{msg.body}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
