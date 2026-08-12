import {
  badRequest,
  isDbConfigured,
  notFound,
  requireApiAuth,
  serverError,
} from "@/lib/control-plane/auth";
import { runControlAction } from "@/lib/control-plane/actions";
import type { ControlAction } from "@/lib/control-plane/types";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ id: string }> };

const ACTIONS: ControlAction[] = ["approve", "cancel", "retry"];

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

  const action = body.action as ControlAction;
  if (!ACTIONS.includes(action)) {
    return badRequest(`action must be one of: ${ACTIONS.join(", ")}`);
  }

  try {
    const result = await runControlAction(
      id,
      action,
      typeof body.actor === "string" ? body.actor : undefined,
    );
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "action failed";
    if (message.includes("not found")) return notFound(message);
    return badRequest(message);
  }
}
