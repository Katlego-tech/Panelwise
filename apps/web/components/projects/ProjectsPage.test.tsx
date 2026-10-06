// @vitest-environment jsdom
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Job, ProjectSummary } from "@/lib/api/types";

import { ProjectsPage } from "./ProjectsPage";

const fetchMock = vi.fn<typeof fetch>();
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: false });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  push.mockReset();
});

const job = (over: Partial<Job> = {}): Job => ({
  id: "j1",
  state: "running",
  stage: "planning",
  progress: 40,
  error: null,
  updated_at: "2026-10-06T07:14:00Z",
  ...over,
});
const project = (over: Partial<ProjectSummary> = {}): ProjectSummary => ({
  id: "p1",
  title: "Lost Property",
  created_at: "2026-10-06T07:14:00Z",
  pages: 9,
  scenes: 12,
  shots: null,
  frames: null,
  job: job(),
  ...over,
});

const tick = () => act(async () => vi.advanceTimersByTimeAsync(2000));

describe("ProjectsPage (web.md §4.1a)", () => {
  it("lists the screenplays newest first under its heading", () => {
    render(<ProjectsPage initial={[project({ title: "B" }), project({ id: "p2", title: "A" })]} />);
    expect(screen.getByRole("heading", { name: "Your screenplays" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["B", "A"]);
  });

  it("an empty list invites an upload", () => {
    render(<ProjectsPage initial={[]} />);
    expect(screen.getByText("No screenplays yet. Upload one to board it.")).toBeInTheDocument();
  });

  it("a list that couldn't load says so", () => {
    render(<ProjectsPage initial={null} />);
    expect(
      screen.getByText("Your screenplays can't be loaded right now. Reload the page to try again."),
    ).toBeInTheDocument();
  });

  it("polls every 2 s while a job is active, and stops when none is", async () => {
    const done = project({ shots: 31, job: job({ state: "done", progress: 60 }) });
    fetchMock.mockResolvedValueOnce(Response.json([done]));
    render(<ProjectsPage initial={[project()]} />);
    expect(screen.getByText("Planning shots")).toBeInTheDocument();

    await tick();
    expect(fetchMock).toHaveBeenCalledWith("/api/projects", expect.objectContaining({ cache: "no-store" }));
    expect(screen.getByText("Shots planned")).toBeInTheDocument();

    await tick();
    await tick();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("doesn't poll when nothing is active", async () => {
    render(<ProjectsPage initial={[project({ job: job({ state: "done" }) })]} />);
    await tick();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the last list when a poll fails, and tries again", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(Response.json([project()]));
    render(<ProjectsPage initial={[project()]} />);
    await tick();
    expect(screen.getByText("Planning shots")).toBeInTheDocument();
    await tick();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  // An accepted upload refreshes the list once (web.md §4.1a, step 5).
  async function upload() {
    const pdf = new File(["%PDF-1.7"], "new.pdf", { type: "application/pdf" });
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [pdf] } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Board this script" }));
    });
  }
  const accepted = () => Response.json({ project: {}, job: {} }, { status: 202 });

  it("keeps trying after a failed refresh, even with nothing active", async () => {
    const done = project({ job: job({ state: "done" }) });
    fetchMock
      .mockResolvedValueOnce(accepted())
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValueOnce(Response.json([project({ id: "p2", title: "New" }), done]));
    render(<ProjectsPage initial={[done]} />);
    await upload();
    expect(screen.queryByText("New")).toBeNull();
    await tick();
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("an older response never overwrites a newer one", async () => {
    let slow!: (r: Response) => void;
    fetchMock
      .mockReturnValueOnce(new Promise((resolve) => (slow = resolve))) // the poll hangs
      .mockResolvedValueOnce(accepted())
      .mockResolvedValueOnce(Response.json([project({ title: "Newer", job: job({ state: "done" }) })]));
    render(<ProjectsPage initial={[project()]} />);
    await tick();
    await upload(); // its refresh lands first
    expect(screen.getByText("Newer")).toBeInTheDocument();
    await act(async () => slow(Response.json([project({ title: "Older" })])));
    expect(screen.getByText("Newer")).toBeInTheDocument();
    expect(screen.queryByText("Older")).toBeNull();
  });

  it("a 401 while polling sends the browser to sign in", async () => {
    fetchMock.mockResolvedValue(Response.json({ error: "unauthorized" }, { status: 401 }));
    render(<ProjectsPage initial={[project()]} />);
    await tick();
    expect(push).toHaveBeenCalledWith("/sign-in");
  });
});
