#!/usr/bin/env tsx
/** MCP server for forge factory control plane (ADR-010).
 *  Run: FORGE_CONTROL_PLANE_URL=… FORGE_API_TOKEN=… npm run mcp
 *  Or from repo root after forge-site install.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const baseUrl = (process.env.FORGE_CONTROL_PLANE_URL ?? "http://127.0.0.1:3000").replace(
  /\/$/,
  "",
);
const token = process.env.FORGE_API_TOKEN ?? "";

async function api<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(`${baseUrl}/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    throw new Error(`${method} ${path} → ${res.status}: ${text}`);
  }
  return data as T;
}

const server = new McpServer({ name: "forge-factory", version: "1.0.0" });

server.tool(
  "list_tasks",
  "List all factory tasks from Postgres",
  {},
  async () => {
    const data = await api<{ tasks: unknown[] }>("GET", "/tasks");
    return {
      content: [{ type: "text", text: JSON.stringify(data.tasks, null, 2) }],
    };
  },
);

server.tool(
  "get_task",
  "Get a task by id",
  { id: z.string().describe("Task id e.g. TASK-008") },
  async ({ id }) => {
    const data = await api<{ task: unknown }>("GET", `/tasks/${encodeURIComponent(id)}`);
    return {
      content: [{ type: "text", text: JSON.stringify(data.task, null, 2) }],
    };
  },
);

server.tool(
  "create_task",
  "Create a new factory task",
  {
    title: z.string(),
    goal: z.string(),
    acceptance_criteria: z.array(z.string()),
    status: z.string().optional(),
    enqueue_plan: z.boolean().optional(),
  },
  async (input) => {
    const data = await api<{ task: unknown }>("POST", "/tasks", input);
    return {
      content: [{ type: "text", text: JSON.stringify(data.task, null, 2) }],
    };
  },
);

server.tool(
  "update_task_status",
  "Update task status or assignee",
  {
    id: z.string(),
    status: z.string().optional(),
    assignee_agent: z.string().nullable().optional(),
  },
  async ({ id, ...patch }) => {
    const data = await api<{ task: unknown }>("PATCH", `/tasks/${encodeURIComponent(id)}`, patch);
    return {
      content: [{ type: "text", text: JSON.stringify(data.task, null, 2) }],
    };
  },
);

server.tool(
  "append_message",
  "Append orchestrator/Slack/system message to a task",
  {
    id: z.string(),
    source: z.string(),
    body: z.string(),
    author: z.string().optional(),
  },
  async ({ id, source, body, author }) => {
    const data = await api<{ message: unknown }>(
      "POST",
      `/tasks/${encodeURIComponent(id)}/messages`,
      { source, body, author },
    );
    return {
      content: [{ type: "text", text: JSON.stringify(data.message, null, 2) }],
    };
  },
);

server.tool(
  "list_messages",
  "List message history for a task",
  { id: z.string() },
  async ({ id }) => {
    const data = await api<{ messages: unknown[] }>(
      "GET",
      `/tasks/${encodeURIComponent(id)}/messages`,
    );
    return {
      content: [{ type: "text", text: JSON.stringify(data.messages, null, 2) }],
    };
  },
);

server.tool(
  "control_action",
  "Run approve, cancel, or retry on a task",
  {
    id: z.string(),
    action: z.enum(["approve", "cancel", "retry"]),
    actor: z.string().optional(),
  },
  async ({ id, action, actor }) => {
    const data = await api<unknown>("POST", `/tasks/${encodeURIComponent(id)}/actions`, {
      action,
      actor,
    });
    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
    };
  },
);

server.tool(
  "claim_work",
  "Claim next proposed task for a worker",
  {
    worker_id: z.string(),
    task_id: z.string().optional(),
    via_queue: z.boolean().optional(),
  },
  async (input) => {
    const data = await api<unknown>("POST", "/jobs/claim", input);
    return {
      content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
    };
  },
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
