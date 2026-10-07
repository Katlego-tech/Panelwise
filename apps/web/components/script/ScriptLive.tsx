"use client";

// Keeps the script page live while its job runs (web.md §4.2, Live): polls the status every 2 s
// and re-renders the page from the server when the job's state or stage changes. Renders nothing.

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import type { Job, ProjectSummary } from "@/lib/api/types";

const POLL_MS = 2000;

export function ScriptLive({ id, job }: { id: string; job: Job }) {
  const router = useRouter();
  const seen = useRef(`${job.state}/${job.stage}`);
  const active = job.state === "queued" || job.state === "running";

  useEffect(() => {
    seen.current = `${job.state}/${job.stage}`;
  }, [job.state, job.stage]);

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/projects/${encodeURIComponent(id)}/status`, { cache: "no-store" });
        if (res.status === 401) {
          router.push("/sign-in");
          return;
        }
        if (!res.ok) return;
        const { job: now } = (await res.json()) as ProjectSummary;
        const key = `${now.state}/${now.stage}`;
        if (key !== seen.current) {
          seen.current = key;
          router.refresh();
        }
      } catch {
        // The next tick tries again.
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [active, id, router]);

  return null;
}
