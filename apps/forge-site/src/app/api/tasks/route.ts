import { loadTasksFromDb } from "@/lib/tasks";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** Legacy route — delegates to v1 API shape. */
export async function GET() {
  try {
    const tasks = await loadTasksFromDb();
    return NextResponse.json({ tasks });
  } catch {
    return NextResponse.json(
      { tasks: [], error: "Failed to load factory tasks" },
      { status: 500 },
    );
  }
}
