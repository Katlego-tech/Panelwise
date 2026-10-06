import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getProject } from "./server";

const fetchMock = vi.fn<typeof fetch>();
const user = { email: null, accessToken: "tok" };

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("API_URL", "http://api.test:8000");
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  fetchMock.mockReset();
});

describe("getProject", () => {
  it("reads one project by its id, encoded as one path segment", async () => {
    fetchMock.mockResolvedValue(Response.json({ id: "p1" }));
    expect(await getProject(user, "p1")).toEqual({ kind: "ok", project: { id: "p1" } });
    await getProject(user, "a/b");
    expect(fetchMock.mock.calls[1]![0]).toBe("http://api.test:8000/api/v1/projects/a%2Fb");
  });

  it("a 404 is not found: missing, malformed and someone else's are the same answer (web.md §6)", async () => {
    fetchMock.mockResolvedValue(Response.json({ error: "not_found" }, { status: 404 }));
    expect(await getProject(user, "p1")).toEqual({ kind: "not-found" });
  });

  it.each([
    ["a 503", () => fetchMock.mockResolvedValue(Response.json({ error: "storage_unavailable" }, { status: 503 }))],
    ["no answer", () => fetchMock.mockRejectedValue(new TypeError("fetch failed"))],
  ])("%s is unavailable", async (_name, arrange) => {
    arrange();
    expect(await getProject(user, "p1")).toEqual({ kind: "unavailable" });
  });
});
