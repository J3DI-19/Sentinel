import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("Traceveil investigation interface", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      const response = path.endsWith("/ai")
        ? { service: "ollama", available: false, model_installed: false }
        : { service: path.endsWith("/db") ? "database" : "api", status: "ok" };
      return Promise.resolve(new Response(JSON.stringify(response), { status: 200 }));
    }));
  });

  it("renders the investigation overview", async () => {
    window.history.replaceState({}, "", "/");
    render(<App />);
    await waitFor(() => expect(screen.getByText("Investigation overview")).toBeInTheDocument());
    expect(screen.getByText("Event activity")).toBeInTheDocument();
    expect(screen.getByText("Recent alerts")).toBeInTheDocument();
    expect(screen.queryByText("Risk distribution")).not.toBeInTheDocument();
    expect(screen.getAllByText("Devices").length).toBeGreaterThan(0);
  });

  it("renders the global Assistant with optional pinned context and switches validated layouts", async () => {
    window.history.replaceState({}, "", "/assistant?case=TV-2026-024&alert=ALT-8831");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Traceveil Assistant" })).toBeInTheDocument();
    expect(screen.getByLabelText("Assistant scope")).toHaveValue("Auto");
    expect(screen.getAllByText("ALT-8831").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: /Summarize what happened on 17 July/i }));
    expect(await screen.findByText("17 July investigation summary")).toBeInTheDocument();
    expect(screen.getByText("Cross-case timeline")).toBeInTheDocument();
    expect(screen.getByText("Related investigations")).toBeInTheDocument();
    expect(screen.getByText("6 sources")).toBeInTheDocument();
    expect(screen.getByText("Rendered from verified investigation data")).toBeInTheDocument();
  });

  it("opens the Assistant in Auto scope without requiring case selection", async () => {
    window.history.replaceState({}, "", "/assistant");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Traceveil Assistant" })).toBeInTheDocument();
    expect(screen.getByLabelText("Assistant scope")).toHaveValue("Auto");
    expect(screen.getByPlaceholderText("Ask Traceveil anything…")).toBeInTheDocument();
    expect(screen.queryByText("No investigation selected")).not.toBeInTheDocument();
    expect(screen.getByText("Traceveil investigation overview")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Assistant scope"), { target: { value: "Specific case" } });
    expect(screen.getByLabelText("Specific case")).toBeInTheDocument();
  });

  it("renders a consolidated live monitoring hierarchy", async () => {
    window.history.replaceState({}, "", "/live");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Live monitor" })).toBeInTheDocument();
    expect(screen.getByText("Live · Capturing")).toBeInTheDocument();
    expect(screen.queryByText("Capture channel operational")).not.toBeInTheDocument();
    expect(screen.queryByText("Capture status")).not.toBeInTheDocument();
    expect(screen.getByText("Live event activity")).toBeInTheDocument();
    expect(screen.getByText("Live event feed")).toBeInTheDocument();
    expect(screen.getByText("Live alerts · Current session")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Explain detection model" })).toHaveAttribute("title", expect.stringContaining("deterministic detection rule"));
    expect(screen.getAllByText("✓ Canonical")).toHaveLength(6);
  });

  it("keeps the cases register dominant and the case summary compact", async () => {
    window.history.replaceState({}, "", "/cases");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Cases" })).toBeInTheDocument();
    expect(screen.getByLabelText("Case status summary")).toHaveTextContent("4Cases2Active1In review1Closed");
    expect(screen.queryByText("Findings generated")).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Evidence" })).toBeInTheDocument();
  });

  it("renders an identity-focused case header and focused case overview", async () => {
    window.history.replaceState({}, "", "/cases/case-024/overview");
    const { container } = render(<App />);
    expect(await screen.findByRole("heading", { name: "Case overview" })).toBeInTheDocument();
    const header = container.querySelector(".case-header");
    expect(header).not.toBeNull();
    expect(within(header as HTMLElement).queryByText("Evidence")).not.toBeInTheDocument();
    expect(within(header as HTMLElement).queryByText("Findings")).not.toBeInTheDocument();
    expect(within(header as HTMLElement).queryByText("Devices")).not.toBeInTheDocument();
    expect(screen.getByText("Incident assessment")).toBeInTheDocument();
    expect(screen.getByText("Assessment confidence")).toBeInTheDocument();
    expect(screen.queryByText("Critical confidence")).not.toBeInTheDocument();
    const tabs = screen.getByRole("navigation", { name: "Case workspace sections" });
    expect(within(tabs).getAllByRole("button")).toHaveLength(8);
    expect(within(tabs).queryByRole("button", { name: "assistant" })).not.toBeInTheDocument();
  });

  it("keeps the shell navigation-only and provides functional global search", async () => {
    window.history.replaceState({}, "", "/cases/case-024/evidence");
    render(<App />);
    expect(screen.queryByText("Collector active")).not.toBeInTheDocument();
    expect(screen.queryByText("Local Workspace")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Notifications" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Investigation Assistant" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "TV-2026-024" })).toBeInTheDocument();
    expect(screen.queryByText("Traceveil", { selector: ".breadcrumbs button" })).not.toBeInTheDocument();
    const search = screen.getByLabelText("Global search");
    fireEvent.change(search, { target: { value: "EVD-2026-8F21" } });
    expect(screen.getByRole("option", { name: /EVD-2026-8F21/ })).toBeInTheDocument();
  });

  it("redirects the legacy case Assistant route with case context", async () => {
    window.history.replaceState({}, "", "/cases/case-024/assistant");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Traceveil Assistant" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/assistant");
    expect(window.location.search).toContain("case=case-024");
  });

  it("renders finding-specific reasoning instead of a page-level risk model", async () => {
    window.history.replaceState({}, "", "/cases/case-024/findings");
    render(<App />);
    expect(await screen.findByText("Selected finding")).toBeInTheDocument();
    expect(screen.getByText("Risk factor breakdown")).toBeInTheDocument();
    expect(screen.getByText("Condition trace")).toBeInTheDocument();
    expect(screen.queryByText("Risk model")).not.toBeInTheDocument();
  });

  it("keeps Analytics deterministic and case Live preservation-focused", async () => {
    window.history.replaceState({}, "", "/cases/case-024/analytics");
    const { unmount } = render(<App />);
    expect(await screen.findByText("Fixed forensic workspace")).toBeInTheDocument();
    expect(screen.queryByText("Visualization Renderer v1")).not.toBeInTheDocument();
    unmount();
    window.history.replaceState({}, "", "/cases/case-024/live");
    render(<App />);
    expect(await screen.findByText("Case capture status")).toBeInTheDocument();
    expect(screen.getByText("Preserved records")).toBeInTheDocument();
    expect(screen.getByText("Evidence continuity")).toBeInTheDocument();
  });

  it("consolidates report approval into final review", async () => {
    window.history.replaceState({}, "", "/cases/case-024/reports");
    render(<App />);
    expect(await screen.findByText("Final review")).toBeInTheDocument();
    expect(screen.getByText("Investigator sign-off")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve report" })).toBeInTheDocument();
    expect(screen.getByText("No email is sent from this mock interface.")).toBeInTheDocument();
  });

  it("renders stateful settings with honest capability boundaries", async () => {
    window.history.replaceState({}, "", "/settings");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText("Frontend settings preview")).toBeInTheDocument();
    const save = screen.getByRole("button", { name: "Save preferences" });
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "Compact evidence rows" }));
    expect(screen.getByText("Unsaved session changes")).toBeInTheDocument();
    fireEvent.click(save);
    expect(screen.getByText(/Settings applied to this browser session/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Model settings/ }));
    expect(screen.getByText("Optional AI runtime")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Email delivery/ }));
    expect(screen.getByText("Delivery service unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save email delivery" })).toBeDisabled();
  });
});
