import fs from "fs";
import path from "path";
import { Pool, type QueryResultRow } from "pg";

let pool: Pool | null = null;
let migrated = false;

export function getPool(): Pool | null {
  const url = process.env.DATABASE_URL?.trim();
  if (!url) return null;
  if (!pool) {
    pool = new Pool({ connectionString: url, max: 10 });
  }
  return pool;
}

export async function runMigrations(): Promise<void> {
  if (migrated) return;
  const p = getPool();
  if (!p) return;
  const schemaPath = path.join(process.cwd(), "src/lib/db/schema.sql");
  const sql = fs.readFileSync(schemaPath, "utf8");
  await p.query(sql);
  migrated = true;
}

export async function query<T extends QueryResultRow = QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<{ rows: T[] }> {
  const p = getPool();
  if (!p) {
    throw new Error("DATABASE_URL not configured");
  }
  if (process.env.FORGE_RUN_MIGRATIONS === "true") {
    await runMigrations();
  }
  return p.query<T>(text, params);
}

export async function withTransaction<T>(
  fn: (client: import("pg").PoolClient) => Promise<T>,
): Promise<T> {
  const p = getPool();
  if (!p) throw new Error("DATABASE_URL not configured");
  const client = await p.connect();
  try {
    await client.query("BEGIN");
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
