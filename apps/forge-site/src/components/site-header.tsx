import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-zinc-50">
          homelab-forge
        </Link>
        <nav className="flex gap-6 text-sm text-zinc-400">
          <Link href="/" className="transition hover:text-zinc-100">
            Home
          </Link>
          <Link href="/dashboard" className="transition hover:text-zinc-100">
            Dashboard
          </Link>
          <a
            href="https://github.com/diestrin/homelab-forge"
            className="transition hover:text-zinc-100"
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
