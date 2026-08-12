import { headers } from "next/headers";
import { NextResponse } from "next/server";

export function getApiToken(): string | undefined {
  return process.env.FORGE_API_TOKEN?.trim() || undefined;
}

export function isDbConfigured(): boolean {
  return Boolean(process.env.DATABASE_URL?.trim());
}

export function unauthorized(): NextResponse {
  return NextResponse.json({ error: "unauthorized" }, { status: 401 });
}

export function badRequest(message: string): NextResponse {
  return NextResponse.json({ error: message }, { status: 400 });
}

export function notFound(message: string): NextResponse {
  return NextResponse.json({ error: message }, { status: 404 });
}

export function serverError(message: string): NextResponse {
  return NextResponse.json({ error: message }, { status: 500 });
}

/** Bearer token auth for /api/v1/* mutation and job routes. */
export async function requireApiAuth(): Promise<NextResponse | null> {
  const expected = getApiToken();
  if (!expected) {
    return serverError("FORGE_API_TOKEN not configured");
  }
  const h = await headers();
  const auth = h.get("authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (!token || token !== expected) {
    return unauthorized();
  }
  return null;
}

/** Optional auth: public read when token absent; require token when configured and provided wrong. */
export async function optionalApiAuthForRead(): Promise<NextResponse | null> {
  const expected = getApiToken();
  if (!expected) return null;
  const h = await headers();
  const auth = h.get("authorization");
  if (!auth) return null;
  const token = auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
  if (token !== expected) return unauthorized();
  return null;
}
