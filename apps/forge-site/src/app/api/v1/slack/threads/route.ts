import {
  badRequest,
  isDbConfigured,
  notFound,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { getSlackThread, saveSlackThread } from "@/lib/control-plane/tasks";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) return serverError("DATABASE_URL not configured");

  const url = new URL(request.url);
  const channelId = url.searchParams.get("channel_id");
  const threadTs = url.searchParams.get("thread_ts");
  if (!channelId || !threadTs) {
    return badRequest("channel_id and thread_ts query params required");
  }

  try {
    const binding = await getSlackThread(channelId, threadTs);
    if (!binding) return notFound("thread binding not found");
    return NextResponse.json({ binding });
  } catch (err) {
    const message = err instanceof Error ? err.message : "lookup failed";
    return serverError(message);
  }
}

export async function POST(request: Request) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  if (!isDbConfigured()) return serverError("DATABASE_URL not configured");

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  const channelId = typeof body.channel_id === "string" ? body.channel_id : "";
  const threadTs = typeof body.thread_ts === "string" ? body.thread_ts : "";
  const taskId = typeof body.task_id === "string" ? body.task_id : "";
  const prUrl = typeof body.pr_url === "string" ? body.pr_url : undefined;

  if (!channelId || !threadTs || !taskId) {
    return badRequest("channel_id, thread_ts, task_id required");
  }

  try {
    await saveSlackThread(channelId, threadTs, taskId, prUrl);
    const binding = await getSlackThread(channelId, threadTs);
    return NextResponse.json({ binding }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "save failed";
    return serverError(message);
  }
}
