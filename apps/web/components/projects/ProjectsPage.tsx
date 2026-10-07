"use client";

// The projects page's live part (web.md §4.1a): the upload panel beside the list, polling
// GET /api/projects every 2 s while any job is queued or running or any frame is active.

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import type { ProjectSummary } from "@/lib/api/types";

import { ProjectList } from "./ProjectList";
import { isActive } from "./rowState";
import { UploadPanel } from "./UploadPanel";

const POLL_MS = 2000;

export function ProjectsPage({ initial }: { initial: ProjectSummary[] | null }) {
  const [projects, setProjects] = useState(initial);
  const router = useRouter();
  // Only the newest request may write the list: an older, slower answer is dropped.
  const latest = useRef(0);

  const refresh = useCallback(async () => {
    const mine = ++latest.current;
    try {
      const res = await fetch("/api/projects", { cache: "no-store" });
      if (res.status === 401) {
        router.push("/sign-in");
        return;
      }
      if (!res.ok) throw new Error(`list answered ${res.status}`);
      const list = (await res.json()) as ProjectSummary[];
      if (mine !== latest.current) return;
      setProjects(list);
    } catch {
      // Keep the last list; the next tick tries again.
    }
  }, [router]);

  const polling = projects?.some(isActive) ?? false;
  useEffect(() => {
    if (!polling) return;
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [polling, refresh]);

  return (
    <main className="mx-auto grid max-w-[1100px] items-start gap-8 px-4 pt-7 pb-12 min-[861px]:grid-cols-2 min-[861px]:gap-12 min-[861px]:px-6 min-[861px]:pt-12 min-[861px]:pb-16">
      <UploadPanel />
      <ProjectList projects={projects} />
    </main>
  );
}
