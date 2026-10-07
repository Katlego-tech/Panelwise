import { describe, expect, it } from "vitest";

import { checkFiles, defaultTitle, fileSize, UPLOAD_COPY, uploadOutcome } from "./upload";

const pdf = (name = "the-keepers-light.pdf", type = "application/pdf") => new File(["%PDF-1.7"], name, { type });

describe("checkFiles (before anything is sent)", () => {
  it("accepts one PDF by type or by name", () => {
    expect(checkFiles([pdf()])).toEqual({ ok: true, file: expect.any(File) });
    expect(checkFiles([pdf("draft.PDF", "")])).toMatchObject({ ok: true });
  });

  it("refuses more than one file", () => {
    expect(checkFiles([pdf(), pdf("b.pdf")])).toEqual({ ok: false, message: "Drop one PDF at a time." });
  });

  it("refuses a file that is neither a PDF by type nor by name with the not_a_pdf copy", () => {
    expect(checkFiles([pdf("notes.docx", "application/msword")])).toEqual({
      ok: false,
      message: UPLOAD_COPY.not_a_pdf,
    });
  });

  it("does nothing for an empty selection", () => {
    expect(checkFiles([])).toBeNull();
  });
});

describe("uploadOutcome (by status and error code, never the message)", () => {
  it("202 is accepted", () => {
    expect(uploadOutcome(202, { project: {}, job: {} })).toEqual({ kind: "accepted" });
  });

  it("400 not_a_pdf", () => {
    expect(uploadOutcome(400, { error: "not_a_pdf" })).toEqual({
      kind: "error",
      message: "This file isn't a PDF. Export the script from your screenwriting app as a PDF and upload that.",
    });
  });

  it("413 from the API or from Vercel's own limit, which isn't JSON", () => {
    const tooLarge = { kind: "error", message: "This PDF is larger than this demo accepts. Upload a smaller file." };
    expect(uploadOutcome(413, { error: "too_large" })).toEqual(tooLarge);
    expect(uploadOutcome(413, null)).toEqual(tooLarge);
  });

  it.each([
    [400, { error: "no_file" }],
    [400, { error: "bad_form" }],
    [411, { error: "length_required" }],
  ])("%i %j: the upload didn't arrive whole", (status, body) => {
    expect(uploadOutcome(status, body)).toEqual({
      kind: "error",
      message: "The upload didn't arrive whole. Choose the file again and try once more.",
    });
  });

  it("401 sends the browser to sign in", () => {
    expect(uploadOutcome(401, { error: "unauthorized" })).toEqual({ kind: "sign-in" });
  });

  it.each([
    [503, { error: "storage_unavailable" }],
    [503, { error: "auth_unavailable" }],
    [500, null],
    [400, { error: "something_new" }],
    [null, null],
  ])("%s %j: can't take uploads right now", (status, body) => {
    expect(uploadOutcome(status, body)).toEqual({
      kind: "error",
      message: "Panelwise can't take uploads right now. Try again in a minute.",
    });
  });

  it("ignores the message text: an unknown code with a familiar message is still unavailable", () => {
    expect(uploadOutcome(400, { error: "x", detail: "not_a_pdf" })).toEqual({
      kind: "error",
      message: UPLOAD_COPY.unavailable,
    });
  });
});

describe("the chosen file", () => {
  it("prefills the title with the file name without .pdf, at most 200 characters", () => {
    expect(defaultTitle("the-keepers-light.pdf")).toBe("the-keepers-light");
    expect(defaultTitle("Draft.PDF")).toBe("Draft");
    expect(defaultTitle(`${"a".repeat(250)}.pdf`)).toHaveLength(200);
  });

  it("shows its size in KB, or MB from 1 MB", () => {
    expect(fileSize(86_000)).toBe("84 KB");
    expect(fileSize(300)).toBe("1 KB");
    expect(fileSize(3_400_000)).toBe("3.2 MB");
  });
});
