import {
  badRequest,
  isDbConfigured,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { appendRunEvents } from "@/lib/control-plane/runs";
import type { RunEvent } from "@/lib/control-plane/types";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type RouteProps = { params: Promise<{ id: string }> };

export async function POST(request: Request, { params }: RouteProps) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }
  const { id } = await params;

  let body: Record<string, unknown> = {};
  try {
    const text = await request.text();
    if (text) body = JSON.parse(text) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  if (!Array.isArray(body.events)) {
    return badRequest("events must be an array");
  }
  const events = body.events.filter(
    (e): e is RunEvent => typeof e === "object" && e !== null,
  );

  try {
    const eventCount = await appendRunEvents(id, events);
    return NextResponse.json({ appended: events.length, event_count: eventCount });
  } catch (err) {
    const message = err instanceof Error ? err.message : "append events failed";
    return badRequest(message);
  }
}
