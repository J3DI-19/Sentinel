import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("Traceveil investigation interface", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      const response = path.endsWith("/dashboard/summary")
        ? { case_count: 1, event_count: 12, active_cases: 1, recent_cases: [{ id: 1, name: "Persisted demo", created_at: "2026-01-01T00:00:00Z", updated_at: null }] }
        : path.includes("/cases?page=")
        ? { items: [{ id: 1, name: "Persisted demo", description: "", case_type: "batch", status: "active", owner: "Investigator", created_at: "2026-01-01T00:00:00Z", updated_at: null }], page: 1, page_size: 100, total: 1 }
        : path.endsWith("/assistant/sessions")
        ? { session_id: "11111111-1111-4111-8111-111111111111", scope: "auto", case_ids: [], reference_ids: [] }
        : path.includes("/live-sessions")
        ? { items: [], page: 1, page_size: 0, total: 0 }
        : path.includes("/live/metrics")
        ? { case_id: 1, session_id: null, device_count: 0, event_count: 0, alert_count: 0, malformed_count: 0, updated_at: null }
        : path.includes("/live/devices")
        ? { items: [], page: 1, page_size: 0, total: 0 }
        : path.endsWith("/ai")
        ? { service: "ollama", available: false, model_installed: false }
        : { service: path.endsWith("/db") ? "database" : "api", status: "ok" };
      return Promise.resolve(new Response(JSON.stringify(response), { status: 200 }));
    }));
  });

  it("renders the investigation overview", async () => {
    window.history.replaceState({}, "", "/");
    render(<App />);
    await waitFor(() => expect(screen.getByText("Investigation overview")).toBeInTheDocument());
    expect(screen.getByText("Canonical events")).toBeInTheDocument();
    expect(screen.getByText("Recent persisted cases")).toBeInTheDocument();
    expect(screen.getByText("Persisted demo")).toBeInTheDocument();
  });

  it("renders the connected Assistant with bounded case context and a safe layout boundary", async () => {
    window.history.replaceState({}, "", "/assistant?case=1&alert=ALT-8831");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Traceveil Assistant" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByText("ready").length).toBeGreaterThan(0));
    expect(screen.getByText("Scoped to persisted case 1")).toBeInTheDocument();
    expect(screen.getByText("Validated data references")).toBeInTheDocument();
    expect(screen.getByText(/Generated code, arbitrary URLs/)).toBeInTheDocument();
  });

  it("opens the Assistant in Auto scope without requiring case selection", async () => {
    window.history.replaceState({}, "", "/assistant");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Traceveil Assistant" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Auto retrieval across persisted cases")).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Ask about persisted investigation evidence…")).toBeInTheDocument();
    expect(screen.getByText("Ask about persisted evidence")).toBeInTheDocument();
    expect(screen.getByText(/Verify AI narration/)).toBeInTheDocument();
  });

  it("renders a consolidated live monitoring hierarchy", async () => {
    window.history.replaceState({}, "", "/live");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Live monitor" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Start capture" })).toBeEnabled());
    expect(screen.getByText("SSE connection")).toBeInTheDocument();
    expect(screen.getByText("Persisted live event feed")).toBeInTheDocument();
    expect(screen.getByText("New deterministic alerts")).toBeInTheDocument();
    expect(screen.getByText("No live events yet")).toBeInTheDocument();
    expect(screen.getByText("Pausing never stops collection or backend analysis.")).toBeInTheDocument();
  });

  it("keeps the cases register dominant and the case summary compact", async () => {
    window.history.replaceState({}, "", "/cases");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Cases" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Case status summary")).toHaveTextContent("1Cases1Active"));
    expect(screen.queryByText("Findings generated")).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Updated (UTC)" })).toBeInTheDocument();
  });

  it("renders a connected case overview without fixture-authored case chrome", async () => {
    window.history.replaceState({}, "", "/cases/1/overview");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Case overview" })).toBeInTheDocument();
    const tabs = screen.getByRole("navigation", { name: "Connected case views" });
    expect(within(tabs).getByRole("button", { name: "reports" })).toBeInTheDocument();
    expect(screen.queryByText("Incident assessment")).not.toBeInTheDocument();
  });

  it("keeps the shell navigation-only and provides functional global search", async () => {
    window.history.replaceState({}, "", "/cases/1/evidence");
    render(<App />);
    expect(screen.queryByText("Collector active")).not.toBeInTheDocument();
    expect(screen.queryByText("Local Workspace")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Notifications" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Investigation Assistant" })).toBeInTheDocument();
    expect(screen.queryByText("Traceveil", { selector: ".breadcrumbs button" })).not.toBeInTheDocument();
    const search = screen.getByLabelText("Global search");
    fireEvent.change(search, { target: { value: "Live Monitor" } });
    expect(screen.getByRole("option", { name: /Live Monitor/ })).toBeInTheDocument();
  });

  it("does not expose legacy fixture-backed case routes", async () => {
    window.history.replaceState({}, "", "/cases/case-024/assistant");
    render(<App />);
    expect(await screen.findByText("Legacy demonstration case unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open cases" })).toBeInTheDocument();
    expect(screen.queryByText("Selected finding")).not.toBeInTheDocument();
  });

  it("renders connected findings without frontend risk calculation", async () => {
    window.history.replaceState({}, "", "/cases/1/findings");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Findings" })).toBeInTheDocument();
    expect(screen.getByText("No findings")).toBeInTheDocument();
    expect(screen.queryByText("Risk model")).not.toBeInTheDocument();
  });

  it("keeps connected analytics backend-authored and links to live capture", async () => {
    window.history.replaceState({}, "", "/cases/1/analytics");
    const { unmount } = render(<App />);
    expect(await screen.findByRole("heading", { name: "Analytics" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Live capture" })).toBeInTheDocument();
    unmount();
    window.history.replaceState({}, "", "/live?case=1");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Live monitor" })).toBeInTheDocument();
    expect(screen.getByText("Accepted records stream after durable persistence.")).toBeInTheDocument();
  });

  it("provides approval-gated connected report delivery", async () => {
    window.history.replaceState({}, "", "/cases/1/reports");
    render(<App />);
    expect(await screen.findByText("Reports and email")).toBeInTheDocument();
    expect(screen.getByText(/email is never sent automatically/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create report" })).toBeInTheDocument();
  });

  it("renders stateful settings with honest capability boundaries", async () => {
    window.history.replaceState({}, "", "/settings");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.getByText("Frontend preference boundary")).toBeInTheDocument();
    const save = screen.getByRole("button", { name: "Save preferences" });
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "Compact evidence rows" }));
    expect(screen.getByText("Unsaved session changes")).toBeInTheDocument();
    fireEvent.click(save);
    expect(screen.getByText(/Settings applied to this browser session/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Model settings/ }));
    expect(screen.getByText("Optional AI runtime")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Email delivery/ }));
    expect(screen.getByText("Delivery is server-configured")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save email delivery" })).toBeDisabled();
  });

  it("routes to a truthful empty import workflow", async () => {
    window.history.replaceState({}, "", "/import");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Import evidence" })).toBeInTheDocument();
    expect(screen.getByText("No validation result")).toBeInTheDocument();
    expect(screen.getAllByText("Mock adapter").length).toBeGreaterThan(0);
    expect(screen.queryByText("northbridge-toniot.csv")).not.toBeInTheDocument();
  });
});
