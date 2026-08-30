import {
  isDbConfigured,
  notFound,
  optionalApiAuthForRead,
  serverError,
} from "@/lib/control-plane/auth";
import { listRuns } from "@/lib/control-plane/runs";
import { getTask } from "@/lib/control-plane/tasks";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type RouteProps = { params: Promise<{ id: string }> };

export async function GET(_request: Request, { params }: RouteProps) {
  const authErr = await optionalApiAuthForRead();
  if (authErr) return authErr;
  if (!isDbConfigured()) {
    return serverError("DATABASE_URL not configured");
  }
  const { id } = await params;
  const task = await getTask(id);
  if (!task) return notFound(`task not found: ${id}`);
  const runs = await listRuns(id);
  return NextResponse.json({ runs });
}
