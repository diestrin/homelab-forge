import fs from "fs";
import path from "path";
import yaml from "yaml";

export interface FactoryTask {
  id: string;
  title: string;
  status: string;
  assignee_agent: string | null;
}

function tasksDirectory(): string {
  if (process.env.FORGE_TASKS_DIR) {
    return process.env.FORGE_TASKS_DIR;
  }
  return path.join(process.cwd(), "../../factory/tasks");
}

export function loadTasks(): FactoryTask[] {
  const dir = tasksDirectory();

  if (!fs.existsSync(dir)) {
    return [];
  }

  const tasks: FactoryTask[] = [];

  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith(".yaml")) {
      continue;
    }

    try {
      const raw = fs.readFileSync(path.join(dir, file), "utf8");
      const doc = yaml.parse(raw) as Record<string, unknown> | null;

      if (
        !doc ||
        typeof doc.id !== "string" ||
        typeof doc.title !== "string" ||
        typeof doc.status !== "string"
      ) {
        continue;
      }

      tasks.push({
        id: doc.id,
        title: doc.title,
        status: doc.status,
        assignee_agent:
          typeof doc.assignee_agent === "string" ? doc.assignee_agent : null,
      });
    } catch {
      // Skip unreadable or malformed task files in v1.
    }
  }

  return tasks.sort((a, b) => a.id.localeCompare(b.id));
}
