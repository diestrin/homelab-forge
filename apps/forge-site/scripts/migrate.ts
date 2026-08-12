#!/usr/bin/env tsx
import { runMigrations } from "../src/lib/db/pool";

async function main() {
  if (!process.env.DATABASE_URL) {
    console.error("DATABASE_URL required");
    process.exit(1);
  }
  await runMigrations();
  console.log("migrations applied");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
