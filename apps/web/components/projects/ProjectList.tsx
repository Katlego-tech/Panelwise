// "Your screenplays" (web.md §4.1a): newest first, as the API orders them.

import type { ProjectSummary } from "@/lib/api/types";

import { ProjectRow } from "./ProjectRow";

export const EMPTY = "No screenplays yet. Upload one to board it.";
export const UNLOADED = "Your screenplays can't be loaded right now. Reload the page to try again.";

export function ProjectList({ projects }: { projects: ProjectSummary[] | null }) {
  return (
    <section aria-labelledby="list-title">
      <h2
        id="list-title"
        className="m-0 mb-3.5 border-b-2 border-ink pb-1.5 font-display text-[22px] leading-[1.1] font-extrabold tracking-[0.03em] uppercase"
      >
        Your screenplays
      </h2>
      {projects === null ? (
        <p className="m-0 text-sm text-ink-2">{UNLOADED}</p>
      ) : projects.length === 0 ? (
        <p className="m-0 text-sm text-ink-2">{EMPTY}</p>
      ) : (
        <ul className="m-0 grid list-none gap-3.5 p-0">
          {projects.map((project) => (
            <ProjectRow key={project.id} project={project} />
          ))}
        </ul>
      )}
    </section>
  );
}
