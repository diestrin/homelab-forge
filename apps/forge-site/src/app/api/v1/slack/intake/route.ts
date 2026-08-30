import {
  badRequest,
  isDbConfigured,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { handleSlackIntake, type IntakeInput } from "@/lib/control-plane/intake";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }

  let body: Record<string, unknown> = {};
  try {
    const text = await request.text();
    if (text) body = JSON.parse(text) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  const kind = body.kind;
  if (kind !== "plan" && kind !== "thread_reply") {
    return badRequest("kind must be plan or thread_reply");
  }
  const channelId = typeof body.channel_id === "string" ? body.channel_id : "";
  const threadTs = typeof body.thread_ts === "string" ? body.thread_ts : "";
  const text = typeof body.text === "string" ? body.text.trim() : "";
  if (!channelId || !threadTs || !text) {
    return badRequest("channel_id, thread_ts, and text are required");
  }

  const input: IntakeInput = {
    kind,
    channel_id: channelId,
    thread_ts: threadTs,
    text,
    author: typeof body.author === "string" ? body.author : undefined,
  };

  try {
    const result = await handleSlackIntake(input);
    return NextResponse.json(result, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "intake failed";
    return badRequest(message);
  }
}
