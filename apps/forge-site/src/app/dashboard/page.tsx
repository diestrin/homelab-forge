import Link from "next/link";
import { loadTasksFromDb } from "@/lib/tasks";

export const dynamic = "force-dynamic";

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

export default async function DashboardPage() {
  const tasks = await loadTasksFromDb();

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <div className="mb-8">
        <h1 className="mb-2 text-3xl font-bold tracking-tight text-zinc-50">
          Factory dashboard
        </h1>
        <p className="text-zinc-400">
          Live tasks from the control plane API (Postgres, ADR-010). Git remains code/config SoT;
          runtime coordination no longer depends on checked-out YAML.
        </p>
      </div>

      {tasks.length === 0 ? (
        <p className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 text-zinc-400">
          No tasks in the database yet. Create work via{" "}
          <code className="rounded bg-zinc-900 px-1.5 py-0.5 font-mono text-sm text-zinc-300">
            /forge plan …
          </code>{" "}
          in Slack or the HTTP/MCP API.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="min-w-full divide-y divide-zinc-800 text-left text-sm">
            <thead className="bg-zinc-900/80">
              <tr>
                <th className="px-4 py-3 font-semibold text-zinc-300">ID</th>
                <th className="px-4 py-3 font-semibold text-zinc-300">Title</th>
                <th className="px-4 py-3 font-semibold text-zinc-300">Status</th>
                <th className="px-4 py-3 font-semibold text-zinc-300">Assignee</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/80 bg-zinc-950/40">
              {tasks.map((task) => (
                <tr key={task.id} className="hover:bg-zinc-900/40">
                  <td className="px-4 py-3 font-mono">
                    <Link
                      href={`/dashboard/${task.id}`}
                      className="text-amber-400/90 hover:text-amber-300"
                    >
                      {task.id}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-zinc-200">{task.title}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${statusBadgeClass(task.status)}`}
                    >
                      {task.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">
                    {task.assignee_agent ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
