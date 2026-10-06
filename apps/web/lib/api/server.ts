// Server-side calls to the API (deploy.md §4: the browser never calls it directly).

import type { CurrentUser } from "@/lib/supabase/server";

import type { Project, ProjectSummary } from "./types";

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

/** The API path of one project: the id is one path segment, whatever it contains. */
export const projectPath = (id: string) => `/projects/${encodeURIComponent(id)}`;

export type ProjectRead = { kind: "ok"; project: Project } | { kind: "not-found" } | { kind: "unavailable" };

/** One project. A 404 covers missing, malformed and someone else's ids alike (web.md §6). */
export async function getProject(user: CurrentUser, id: string): Promise<ProjectRead> {
  try {
    const res = await apiFetch(projectPath(id), user);
    if (res.status === 404) return { kind: "not-found" };
    if (!res.ok) return { kind: "unavailable" };
    return { kind: "ok", project: (await res.json()) as Project };
  } catch {
    return { kind: "unavailable" };
  }
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
