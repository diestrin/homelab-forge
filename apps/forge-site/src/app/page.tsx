import Link from "next/link";

const components = [
  {
    name: "Declarative host",
    detail: "Nix flakes and Home Manager on Ubuntu — reproducible tooling and sysctl/journald.",
  },
  {
    name: "Sandbox platform",
    detail: "Layered profiles (trusted → devcontainer → k8s-workload) isolate project work.",
  },
  {
    name: "Local Kubernetes",
    detail: "k3s with Traefik Ingress, cert-manager, and NetworkPolicies on 80/443.",
  },
  {
    name: "Secrets & GitOps",
    detail: "HashiCorp Vault + External Secrets; Argo CD syncs cluster state from main.",
  },
  {
    name: "Agentic factory",
    detail: "Git-backed tasks, Slack plan gate, Cursor SDK workers, human review before merge.",
  },
  {
    name: "Host IDS",
    detail: "In-tree host-watch monitors the NUC; alerts via ntfy without secrets in git.",
  },
];

const factorySteps = [
  {
    step: "1. Intake",
    text: "Operator describes work in Slack. The orchestrator drafts a plan PR with task YAML.",
  },
  {
    step: "2. Plan gate",
    text: "Thread feedback refines the plan. Explicit approval moves the task to proposed.",
  },
  {
    step: "3. Worker",
    text: "A sandboxed worker claims the task, implements in a git worktree, and opens/updates the PR.",
  },
  {
    step: "4. Review",
    text: "Humans run the review checklist. No auto-merge for production-facing changes.",
  },
  {
    step: "5. Deploy",
    text: "Merge to main. Argo CD converges manifests — the only steady-state deploy path.",
  },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <section className="mb-16">
        <p className="mb-3 text-sm font-medium uppercase tracking-widest text-amber-400/90">
          Open source · portfolio-grade homelab
        </p>
        <h1 className="mb-4 text-4xl font-bold tracking-tight text-zinc-50 sm:text-5xl">
          Forge Software Factory
        </h1>
        <p className="max-w-2xl text-lg leading-relaxed text-zinc-400">
          homelab-forge turns a single powerful workstation into a declarative software
          forge: remote development, sandboxed agents, local Kubernetes, Vault-backed
          secrets, and a git-native factory pipeline — all public, all review-gated.
        </p>
        <div className="mt-8 flex flex-wrap gap-4">
          <Link
            href="/dashboard"
            className="rounded-lg bg-amber-500 px-5 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-amber-400"
          >
            View task dashboard
          </Link>
          <a
            href="https://github.com/diestrin/homelab-forge"
            className="rounded-lg border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-zinc-900"
            target="_blank"
            rel="noopener noreferrer"
          >
            Browse the repo
          </a>
        </div>
      </section>

      <section className="mb-16">
        <h2 className="mb-6 text-2xl font-semibold text-zinc-100">Components</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {components.map((item) => (
            <article
              key={item.name}
              className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5"
            >
              <h3 className="mb-2 font-semibold text-zinc-50">{item.name}</h3>
              <p className="text-sm leading-relaxed text-zinc-400">{item.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-6 text-2xl font-semibold text-zinc-100">
          How the factory works
        </h2>
        <ol className="space-y-4">
          {factorySteps.map((item) => (
            <li
              key={item.step}
              className="flex gap-4 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5"
            >
              <span className="shrink-0 font-mono text-sm font-semibold text-amber-400">
                {item.step}
              </span>
              <p className="text-sm leading-relaxed text-zinc-300">{item.text}</p>
            </li>
          ))}
        </ol>
      </section>
    </main>
  );
}
