// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppBar } from "./AppBar";

describe("AppBar (web.md §6 component tree, projects.png, script.png)", () => {
  it("projects: the wordmark home, who is signed in, and the actions", () => {
    render(<AppBar email="judge@panelwise.demo" actions={<button type="button">Sign out</button>} />);
    expect(screen.getByRole("link", { name: "Panelwise" })).toHaveAttribute("href", "/projects");
    expect(screen.getByText("judge@panelwise.demo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("a project: its title and tabs, the current one marked, Comic disabled with its tooltip", () => {
    render(<AppBar email="judge@panelwise.demo" project={{ id: "p1", title: "The Keeper's Light" }} tab="script" />);
    expect(screen.getByText("The Keeper's Light")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Project" });
    expect(nav).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Script" })).toHaveAttribute("href", "/projects/p1/script");
    expect(screen.getByRole("link", { name: "Script" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Storyboard" })).toHaveAttribute("href", "/projects/p1/storyboard");
    expect(screen.getByRole("link", { name: "Storyboard" })).not.toHaveAttribute("aria-current");
    const comic = screen.getByText("Comic");
    expect(comic).toHaveAttribute("aria-disabled", "true");
    expect(comic).toHaveAttribute("title", "Comic pages aren't built yet");
    expect(comic).not.toHaveAttribute("href");
  });
});
