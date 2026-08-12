import { isDbConfigured } from "@/lib/control-plane/auth";
import { runMigrations } from "@/lib/db/pool";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  if (!isDbConfigured()) {
    return NextResponse.json({ ok: true, db: false, message: "DATABASE_URL not set" });
  }
  try {
    if (process.env.FORGE_RUN_MIGRATIONS === "true") {
      await runMigrations();
    }
    return NextResponse.json({ ok: true, db: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "health check failed";
    return NextResponse.json({ ok: false, db: true, error: message }, { status: 503 });
  }
}
