// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UploadPanel } from "./UploadPanel";

const fetchMock = vi.fn<typeof fetch>();
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  fetchMock.mockReset();
  push.mockReset();
});

const pdf = (name = "the-keepers-light.pdf") => new File(["%PDF-1.7 ".repeat(9000)], name, { type: "application/pdf" });
const fileInput = () => document.querySelector<HTMLInputElement>('input[type="file"]')!;

async function choose(file = pdf()) {
  const user = userEvent.setup();
  await user.upload(fileInput(), file);
  return user;
}

describe("UploadPanel (web.md §4.1a)", () => {
  it("idle: the drop zone is a label over the file input, with the reference copy", () => {
    render(<UploadPanel onAccepted={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Board your script" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Drop a screenplay PDF here, or choose a file/)).toBe(fileInput());
    expect(fileInput()).toHaveAttribute("accept", "application/pdf");
    expect(
      screen.getByText("Export it from your screenwriting app so the text can be read. Scanned pages can't be."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Board this script" })).toBeNull();
  });

  it("chosen: name, size, a different-file action, the title prefilled, the button", async () => {
    render(<UploadPanel onAccepted={vi.fn()} />);
    await choose();
    expect(screen.getByText("the-keepers-light.pdf")).toBeInTheDocument();
    expect(screen.getByText("79 KB")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Choose a different file" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("the-keepers-light");
    expect(screen.getByLabelText("Title")).toHaveAttribute("maxlength", "200");
    expect(screen.getByRole("button", { name: "Board this script" })).toBeEnabled();
  });

  it("sends the file and the title, disabled while it uploads, then resets and refreshes the list", async () => {
    const onAccepted = vi.fn();
    let answer!: (r: Response) => void;
    fetchMock.mockReturnValue(new Promise((resolve) => (answer = resolve)));
    render(<UploadPanel onAccepted={onAccepted} />);
    const user = await choose();
    await user.clear(screen.getByLabelText("Title"));
    await user.type(screen.getByLabelText("Title"), "The Keeper's Light");
    await user.click(screen.getByRole("button", { name: "Board this script" }));

    expect(screen.getByRole("button", { name: "Uploading…" })).toBeDisabled();
    expect(screen.getByLabelText("Title")).toBeDisabled();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/projects");
    expect(init?.method).toBe("POST");
    const body = init?.body as FormData;
    expect((body.get("file") as File).name).toBe("the-keepers-light.pdf");
    expect(body.get("title")).toBe("The Keeper's Light");

    answer(Response.json({ project: {}, job: {} }, { status: 202 }));
    await waitFor(() => expect(onAccepted).toHaveBeenCalledOnce());
    expect(screen.queryByLabelText("Title")).toBeNull();
    expect(screen.getByText(/Drop a screenplay PDF here/)).toBeInTheDocument();
  });

  it("an error keeps the file and title and sits above the button", async () => {
    fetchMock.mockResolvedValue(Response.json({ error: "too_large" }, { status: 413 }));
    render(<UploadPanel onAccepted={vi.fn()} />);
    const user = await choose();
    await user.click(screen.getByRole("button", { name: "Board this script" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("This PDF is larger than this demo accepts. Upload a smaller file.");
    expect(screen.getByLabelText("Title")).toHaveValue("the-keepers-light");
    expect(alert.compareDocumentPosition(screen.getByRole("button", { name: "Board this script" }))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  it("no response at all: can't take uploads right now", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<UploadPanel onAccepted={vi.fn()} />);
    const user = await choose();
    await user.click(screen.getByRole("button", { name: "Board this script" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Panelwise can't take uploads right now. Try again in a minute.",
    );
  });

  it("a 401 sends the browser to sign in", async () => {
    fetchMock.mockResolvedValue(Response.json({ error: "unauthorized" }, { status: 401 }));
    render(<UploadPanel onAccepted={vi.fn()} />);
    const user = await choose();
    await user.click(screen.getByRole("button", { name: "Board this script" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/sign-in"));
  });

  it("dropping two files is refused before anything is sent", () => {
    render(<UploadPanel onAccepted={vi.fn()} />);
    const zone = screen.getByText(/Drop a screenplay PDF here/).closest("[data-dropzone]")!;
    fireEvent.drop(zone, { dataTransfer: { files: [pdf("a.pdf"), pdf("b.pdf")] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Drop one PDF at a time.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("a dropped PDF is chosen, and a drag over the zone tints it", () => {
    render(<UploadPanel onAccepted={vi.fn()} />);
    const zone = screen.getByText(/Drop a screenplay PDF here/).closest("[data-dropzone]")!;
    fireEvent.dragOver(zone, { dataTransfer: { files: [] } });
    expect(zone).toHaveAttribute("data-dragging", "true");
    fireEvent.drop(zone, { dataTransfer: { files: [pdf("kite.pdf")] } });
    expect(screen.getByText("kite.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("kite");
  });

  it("a file that isn't a PDF gets the not-a-PDF copy", () => {
    render(<UploadPanel onAccepted={vi.fn()} />);
    const zone = screen.getByText(/Drop a screenplay PDF here/).closest("[data-dropzone]")!;
    fireEvent.drop(zone, { dataTransfer: { files: [new File(["x"], "notes.docx", { type: "application/msword" })] } });
    expect(screen.getByRole("alert")).toHaveTextContent("This file isn't a PDF.");
  });
});
