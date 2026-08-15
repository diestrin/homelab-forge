import Link from "next/link";
import { FaqAccordion } from "@/components/landing/faq-accordion";
import { ForgeBackground } from "@/components/landing/forge-background";
import {
  IconDeclarativeHost,
  IconDeploy,
  IconFactory,
  IconHostWatch,
  IconIntake,
  IconKubernetes,
  IconPlanGate,
  IconReview,
  IconSandbox,
  IconSecretsGitops,
  IconWorker,
} from "@/components/landing/icons";

const components = [
  {
    name: "Declarative host",
    detail:
      "Nix flakes and Home Manager on Ubuntu — reproducible tooling, sysctl, and journald without drift.",
    Icon: IconDeclarativeHost,
  },
  {
    name: "Sandbox platform",
    detail:
      "Layered profiles from trusted shell to devcontainer to k8s workload — project work stays isolated.",
    Icon: IconSandbox,
  },
  {
    name: "Local Kubernetes",
    detail:
      "k3s with Traefik Ingress, cert-manager, and NetworkPolicies serving HTTPS on your own hardware.",
    Icon: IconKubernetes,
  },
  {
    name: "Secrets & GitOps",
    detail:
      "HashiCorp Vault holds secrets; External Secrets syncs them; Argo CD converges cluster state from main.",
    Icon: IconSecretsGitops,
  },
  {
    name: "Agentic factory",
    detail:
      "Git-backed tasks, Slack plan gate, Cursor SDK workers, and human review before anything reaches production.",
    Icon: IconFactory,
  },
  {
    name: "Host IDS",
    detail:
      "In-tree host-watch monitors the NUC for unexpected listeners and process patterns — alerts via ntfy.",
    Icon: IconHostWatch,
  },
];

const factorySteps = [
  {
    label: "Intake",
    text: "You describe work in Slack. The orchestrator drafts a plan PR with a task YAML and scope.",
    Icon: IconIntake,
  },
  {
    label: "Plan gate",
    text: "Thread feedback refines the plan. Explicit approval moves the task from planning to proposed.",
    Icon: IconPlanGate,
  },
  {
    label: "Worker",
    text: "A sandboxed worker claims the task, implements in a git worktree, and opens or updates the PR.",
    Icon: IconWorker,
  },
  {
    label: "Review",
    text: "Humans run the review checklist. Production-facing changes never auto-merge.",
    Icon: IconReview,
  },
  {
    label: "Deploy",
    text: "Merge to main. Argo CD syncs manifests — the only steady-state deploy path for cluster apps.",
    Icon: IconDeploy,
  },
];

const faqItems = [
  {
    question: "What is homelab-forge?",
    answer:
      "homelab-forge is an open-source portfolio project that turns a single powerful workstation into a software forge: declarative host config, sandboxed development, local Kubernetes, Vault-backed secrets, and a git-native agent factory — all review-gated and documented in public.",
  },
  {
    question: "How does the factory pipeline work?",
    answer:
      "Work starts as a git-backed task YAML. The orchestrator drafts a plan PR; after operator approval a worker implements in an isolated worktree and opens an implementation PR. Humans review against the checklist, merge to main, and Argo CD deploys cluster changes. Code history on main is the audit trail.",
  },
  {
    question: "How do operators interact with the factory?",
    answer:
      "Primary intake is Slack: describe the goal in a thread, iterate on the plan, and approve with an explicit command when ready. The task dashboard on this site shows live status, messages, and PR links. Operators do not kubectl apply Argo-managed apps for steady-state deploys.",
  },
  {
    question: "What is automated vs what needs a human?",
    answer:
      "Agents draft plans, implement code, and run CI — but plan approval, PR review, and merge to main stay human-gated. Argo CD automates cluster convergence after merge; it does not bypass review. Secrets never land in git; Vault is the system of record.",
  },
  {
    question: "How does Argo CD fit into deploys?",
    answer:
      "Argo CD watches the main branch and syncs Kubernetes manifests under k8s/. When a forge-site or other app PR merges, CI builds a new container image and manifest updates trigger a sync. Steady-state deploys are merge → Argo — not manual kubectl apply.",
  },
  {
    question: "Is this safe to expose on the public internet?",
    answer:
      "The repo and this landing page are public by design. SSH is hardened, UFW default-denies, host-watch alerts on unexpected listeners, and admin surfaces stay off WAN. It is a homelab demo — not multi-tenant production — but the posture is documented and intentional.",
  },
];

export default function Home() {
  return (
    <div className="relative">
      <section className="relative overflow-hidden border-b border-forge-ash/60">
        <ForgeBackground />
        <div className="forge-grid-bg absolute inset-0 opacity-40" aria-hidden="true" />
        <div className="relative mx-auto max-w-5xl px-6 pb-20 pt-16 sm:pb-28 sm:pt-24">
          <p className="mb-4 font-mono text-xs uppercase tracking-[0.2em] text-forge-steel">
            Open source · portfolio-grade homelab
          </p>
          <h1 className="font-display text-balance text-4xl leading-[1.1] tracking-tight text-zinc-50 sm:text-6xl">
            A software forge
            <span className="block text-forge-spark">on your own metal</span>
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-forge-steel">
            homelab-forge turns a home workstation into a declarative platform: remote
            development, sandboxed agents, local Kubernetes, Vault-backed secrets, and a
            git-native factory pipeline — public, review-gated, and GitOps-deployed.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link
              href="/dashboard"
              className="rounded-lg bg-forge-ember px-5 py-2.5 text-sm font-semibold text-forge-void transition hover:bg-forge-spark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forge-ember"
            >
              View task dashboard
            </Link>
            <a
              href="https://github.com/diestrin/homelab-forge"
              className="rounded-lg border border-forge-ash px-5 py-2.5 text-sm font-medium text-zinc-200 transition hover:border-forge-steel hover:bg-forge-slate/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forge-steel"
              target="_blank"
              rel="noopener noreferrer"
            >
              Browse the repo
            </a>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-5xl px-6 py-16 sm:py-20">
        <section className="mb-20 sm:mb-28" aria-labelledby="components-heading">
          <div className="mb-10 max-w-xl">
            <p className="mb-2 font-mono text-xs uppercase tracking-[0.15em] text-forge-ember">
              Platform stack
            </p>
            <h2 id="components-heading" className="font-display text-3xl text-zinc-50 sm:text-4xl">
              What the forge is built from
            </h2>
            <p className="mt-3 text-forge-smoke">
              Six layers that together turn one NUC into a credible open-source infrastructure
              story — each with a defined role and public documentation.
            </p>
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {components.map((item) => (
              <article
                key={item.name}
                className="group rounded-xl border border-forge-ash bg-forge-slate/30 p-5 transition hover:border-forge-ember/40 hover:bg-forge-slate/50"
              >
                <div className="mb-4 inline-flex rounded-lg border border-forge-ash bg-forge-void/60 p-2.5 text-forge-ember transition group-hover:border-forge-ember/30 group-hover:text-forge-spark">
                  <item.Icon className="h-8 w-8" />
                </div>
                <h3 className="mb-2 font-semibold text-zinc-50">{item.name}</h3>
                <p className="text-sm leading-relaxed text-forge-smoke">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mb-20 sm:mb-28" aria-labelledby="factory-heading">
          <div className="mb-10 max-w-xl">
            <p className="mb-2 font-mono text-xs uppercase tracking-[0.15em] text-forge-ember">
              Factory pipeline
            </p>
            <h2 id="factory-heading" className="font-display text-3xl text-zinc-50 sm:text-4xl">
              From Slack thread to running cluster
            </h2>
            <p className="mt-3 text-forge-smoke">
              Every change follows the same path: plan, approve, implement, review, merge,
              sync. Order matters — each stage gates the next.
            </p>
          </div>
          <ol className="relative space-y-0">
            {factorySteps.map((item, index) => (
              <li
                key={item.label}
                className="relative flex gap-5 border-l border-forge-ash pb-10 pl-8 last:border-transparent last:pb-0 sm:gap-6 sm:pl-10"
              >
                <span
                  className="absolute -left-3 flex h-6 w-6 items-center justify-center rounded-full border border-forge-ember/50 bg-forge-void font-mono text-[10px] font-medium text-forge-spark"
                  aria-hidden="true"
                >
                  {index + 1}
                </span>
                <div className="shrink-0 rounded-lg border border-forge-ash bg-forge-slate/40 p-2 text-forge-steel">
                  <item.Icon className="h-6 w-6" />
                </div>
                <div className="min-w-0 pt-0.5">
                  <h3 className="font-semibold text-zinc-100">{item.label}</h3>
                  <p className="mt-1 text-sm leading-relaxed text-forge-smoke">{item.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="faq-heading">
          <div className="mb-10 max-w-xl">
            <p className="mb-2 font-mono text-xs uppercase tracking-[0.15em] text-forge-ember">
              Common questions
            </p>
            <h2 id="faq-heading" className="font-display text-3xl text-zinc-50 sm:text-4xl">
              FAQ
            </h2>
            <p className="mt-3 text-forge-smoke">
              How Forge works, who approves what, and where automation stops.
            </p>
          </div>
          <FaqAccordion items={faqItems} />
        </section>
      </main>
    </div>
  );
}
