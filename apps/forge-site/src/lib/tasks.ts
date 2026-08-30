import { listMessages } from "@/lib/control-plane/messages";
import { getRun, listRuns } from "@/lib/control-plane/runs";
import { getTask, listTasks } from "@/lib/control-plane/tasks";
import { isDbConfigured } from "@/lib/control-plane/auth";
import type { AgentRun, FactoryTask, TaskMessage } from "@/lib/control-plane/types";

export type { AgentRun, FactoryTask, TaskMessage };

export async function loadTasksFromDb(): Promise<FactoryTask[]> {
  if (!isDbConfigured()) return [];
  try {
    return await listTasks();
  } catch {
    return [];
  }
}

export async function loadTaskFromDb(id: string): Promise<FactoryTask | null> {
  if (!isDbConfigured()) return null;
  try {
    return await getTask(id);
  } catch {
    return null;
  }
}

export async function loadMessagesFromDb(taskId: string): Promise<TaskMessage[]> {
  if (!isDbConfigured()) return [];
  try {
    return await listMessages(taskId);
  } catch {
    return [];
  }
}

export async function loadRunsFromDb(taskId: string): Promise<AgentRun[]> {
  if (!isDbConfigured()) return [];
  try {
    return await listRuns(taskId);
  } catch {
    return [];
  }
}

export async function loadRunFromDb(runId: string): Promise<AgentRun | null> {
  if (!isDbConfigured()) return null;
  try {
    return await getRun(runId);
  } catch {
    return null;
  }
}
