import fs from "fs";
import path from "path";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const specPath = path.join(process.cwd(), "docs/openapi.yaml");
  const yaml = fs.readFileSync(specPath, "utf8");
  return new NextResponse(yaml, {
    headers: { "Content-Type": "application/yaml; charset=utf-8" },
  });
}
