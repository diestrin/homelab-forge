import {
  badRequest,
  isDbConfigured,
  notFound,
  optionalApiAuthForRead,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { appendMessage, listMessages } from "@/lib/control-plane/messages";
import { getTask } from "@/lib/control-plane/tasks";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

export async function GET(_request: Request, { params }: Params) {
  const authErr = await optionalApiAuthForRead();
  if (authErr) return authErr;
  const { id } = await params;
  if (!isDbConfigured()) {
    return NextResponse.json({ messages: [], db: false });
  }
  try {
    const task = await getTask(id);
    if (!task) return notFound(`task not found: ${id}`);
    const messages = await listMessages(id);
    return NextResponse.json({ messages, db: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "failed to list messages";
    return serverError(message);
  }
}

export async function POST(request: Request, { params }: Params) {
  const authErr = await requireApiAuth();
  if (authErr) return authErr;
  const { id } = await params;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }

  let body: Record<string, unknown>;
  try {
    body = (await request.json()) as Record<string, unknown>;
  } catch {
    return badRequest("invalid JSON body");
  }

  const messageBody = typeof body.body === "string" ? body.body : "";
  if (!messageBody) return badRequest("body required");

  try {
    const task = await getTask(id);
    if (!task) return notFound(`task not found: ${id}`);
    const message = await appendMessage({
      task_id: id,
      source: typeof body.source === "string" ? body.source : "system",
      author: typeof body.author === "string" ? body.author : null,
      body: messageBody,
      metadata:
        body.metadata && typeof body.metadata === "object"
          ? (body.metadata as Record<string, unknown>)
          : {},
    });
    return NextResponse.json({ message }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "failed to append message";
    return serverError(message);
  }
}
