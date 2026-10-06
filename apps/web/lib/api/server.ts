// Server-side calls to the API (deploy.md §4: the browser never calls it directly).

import type { CurrentUser } from "@/lib/supabase/server";

import type { ProjectSummary } from "./types";

export function apiUrl(): string {
  return process.env.API_URL ?? "http://localhost:8000";
}

export function apiFetch(path: string, user: CurrentUser, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${user.accessToken}`);
  return fetch(`${apiUrl()}/api/v1${path}`, { cache: "no-store", ...init, headers });
}

/** The 401 every route handler gives a signed-out caller: the API's own shape (web.md §4.0). */
export const unauthorized = () => Response.json({ error: "unauthorized" }, { status: 401 });
export const unreachable = () => Response.json({ error: "api_unreachable" }, { status: 503 });

/** The API's answer, status and body unchanged. */
export function relay(res: Response): Response {
  return new Response(res.body, {
    status: res.status,
    headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
  });
}

/** The signed-in user's projects, newest first; null when the API can't answer with them. */
export async function listProjects(user: CurrentUser): Promise<ProjectSummary[] | null> {
  try {
    const res = await apiFetch("/projects", user);
    return res.ok ? ((await res.json()) as ProjectSummary[]) : null;
  } catch {
    return null;
  }
}
