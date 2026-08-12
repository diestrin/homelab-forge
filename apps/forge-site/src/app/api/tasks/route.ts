import { loadTasks } from "@/lib/tasks";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json({ tasks: loadTasks() });
  } catch {
    return NextResponse.json(
      { tasks: [], error: "Failed to load factory tasks" },
      { status: 500 },
    );
  }
}
