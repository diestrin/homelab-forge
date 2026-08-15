import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-forge-ash/80 bg-forge-void/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link
          href="/"
          className="font-display text-lg tracking-tight text-zinc-50 transition hover:text-forge-spark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forge-ember"
        >
          homelab-forge
        </Link>
        <nav className="flex gap-6 text-sm text-forge-smoke">
          <Link
            href="/"
            className="transition hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forge-steel"
          >
            Home
          </Link>
          <Link
            href="/dashboard"
            className="transition hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forge-steel"
          >
            Dashboard
          </Link>
          <a
            href="https://github.com/diestrin/homelab-forge"
            className="transition hover:text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forge-steel"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
        </nav>
      </div>
    </header>
  );
}
