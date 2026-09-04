import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConnectedCaseWorkspaceV3Page } from "./ConnectedCaseWorkspaceV3Page";

const summary = (analysisId: string | null) => ({ case: { id: 7, name: "Case Seven" }, event_count: 2, entity_count: 1, finding_count: 0, alert_count: 0, incident_count: 0, maximum_risk: 0, analysis_id: analysisId });
const page = (items: Record<string, unknown>[]) => ({ items, page: 1, page_size: 50, total: items.length });
const jsonResponse = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { "Content-Type": "application/json" } });
function respond(routes: Record<string, unknown>) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
    const path = new URL(String(input), "http://traceveil.test").pathname;
    const match = Object.entries(routes).find(([suffix]) => path.endsWith(suffix));
    return Promise.resolve(new Response(JSON.stringify(match?.[1] ?? { code: "not_found", message: "Not found", retryable: false }), { status: match ? 200 : 404, headers: { "Content-Type": "application/json" } }));
  }));
}

describe("ConnectedCaseWorkspaceV3Page", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("distinguishes no analysis from a successful zero-finding analysis", async () => {
    respond({ "/cases/7/summary": summary(null), "/cases/7/findings": page([]) });
    const { unmount } = render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" navigate={vi.fn()}/>);
    expect(await screen.findByText("No analysis has run")).toBeInTheDocument(); unmount();
    respond({ "/cases/7/summary": summary("analysis-1"), "/cases/7/findings": page([]) });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" navigate={vi.fn()}/>);
    expect(await screen.findByText("Analysis completed with no findings")).toBeInTheDocument();
  });

  it("opens an exact persisted reference outside the current page", async () => {
    const evidenceId = "11111111-1111-4111-8111-111111111111";
    respond({ "/cases/7/summary": summary("analysis-1"), "/cases/7/evidence": page([]), [`/cases/7/evidence/${evidenceId}`]: { evidence_id: evidenceId, original_name: "source.csv", source_type: "simulation", sha256: "abc", issues: [] } });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/evidence" search={`?evidence=${evidenceId}`} navigate={vi.fn()}/>);
    expect(await screen.findByLabelText(`Details for ${evidenceId}`)).toHaveTextContent("source.csv");
    expect(screen.queryByText("Source reference unavailable")).not.toBeInTheDocument();
  });

  it("keeps results visible when a source reference is stale and links supporting records", async () => {
    const eventId = "22222222-2222-4222-8222-222222222222"; const evidenceId = "33333333-3333-4333-8333-333333333333"; const navigate = vi.fn();
    respond({ "/cases/7/summary": summary("analysis-1"), "/cases/7/findings": page([{ finding_id: "finding-1", title: "Persisted finding", severity: "high", rule_id: "RULE-1", event_ids: [eventId], evidence_ids: [evidenceId], condition_trace: [{ field: "label", matched: true }], risk: { score: 80, factors: [{ name: "severity", weighted_points: 30 }] } }]) });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" navigate={navigate}/>);
    fireEvent.click(await screen.findByRole("button", { name: "Inspect finding-1" }));
    expect(screen.getByLabelText("Details for finding-1")).toHaveTextContent("condition trace");
    fireEvent.click(screen.getByRole("button", { name: eventId }));
    expect(navigate).toHaveBeenCalledWith(`/cases/7/events?event=${eventId}`);
    fireEvent.click(screen.getByRole("button", { name: evidenceId }));
    expect(navigate).toHaveBeenCalledWith(`/cases/7/evidence?evidence=${evidenceId}`);

    respond({ "/cases/7/summary": summary("analysis-1"), "/cases/7/evidence": page([{ evidence_id: evidenceId, original_filename: "visible.csv" }]) });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/evidence" search="?evidence=not-a-uuid" navigate={vi.fn()}/>);
    expect(await screen.findByText("Source reference unavailable")).toBeInTheDocument();
    expect(screen.getByText("visible.csv")).toBeInTheDocument();
  });

  it("lists persisted analysis history and opens the selected snapshot", async () => {
    const latestId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; const historicalId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"; const navigate = vi.fn();
    respond({ "/cases/7/summary": summary(latestId), "/cases/7/analyses": page([
      { analysis_id: latestId, case_id: 7, status: "completed", created_at: "2026-09-01T12:00:00Z" },
      { analysis_id: historicalId, case_id: 7, status: "completed", created_at: "2026-08-31T12:00:00Z" },
    ]) });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/history" navigate={navigate}/>);
    expect(await screen.findByText("2 persisted snapshots")).toBeInTheDocument();
    expect(screen.getAllByText("Latest").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "View results" }));
    expect(navigate).toHaveBeenCalledWith(`/cases/7/findings?analysis=${historicalId}`);
  });

  it("loads and preserves an explicitly selected historical snapshot", async () => {
    const latestId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; const historicalId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"; const navigate = vi.fn();
    respond({ "/cases/7/summary": summary(latestId), "/cases/7/findings": page([{ finding_id: "historical-finding", title: "Historical finding", severity: "medium" }]), [`/cases/7/analyses/${historicalId}`]: { analysis_id: historicalId, case_id: 7 } });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" search={`?analysis=${historicalId}`} navigate={navigate}/>);
    expect(await screen.findByText("Historical snapshot")).toBeInTheDocument();
    expect(screen.getByText(historicalId)).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`/cases/7/findings?page=1&page_size=50&analysis_id=${historicalId}`))).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "timeline" }));
    expect(navigate).toHaveBeenCalledWith(`/cases/7/timeline?analysis=${historicalId}`);
  });

  it("loads historical chart data and rejects malformed snapshot IDs", async () => {
    const latestId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; const historicalId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
    respond({ "/cases/7/summary": summary(latestId), "/cases/7/charts": page([{ series: "event_type", category: "motion", value: 2 }]), "/cases/7/graph": { nodes: [], edges: [], truncated: false }, [`/cases/7/analyses/${historicalId}`]: { analysis_id: historicalId, case_id: 7 } });
    const { unmount } = render(<ConnectedCaseWorkspaceV3Page path="/cases/7/charts" search={`?analysis=${historicalId}`} navigate={vi.fn()}/>);
    expect(await screen.findByRole("heading", { name: "Event types" })).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`/cases/7/charts?analysis_id=${historicalId}`))).toBe(true); unmount();

    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" search="?analysis=invalid" navigate={vi.fn()}/>);
    expect(await screen.findByText("Selected analysis unavailable")).toBeInTheDocument();
    expect(screen.getByText(/selected analysis ID is malformed/i)).toBeInTheDocument();
  });
  it("refreshes the exact filtered page and selected snapshot", async () => {
    const analysisId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; const requests: string[] = [];
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://traceveil.test");
      if (url.pathname.endsWith("/cases/7/summary")) return Promise.resolve(jsonResponse(summary(analysisId)));
      if (url.pathname.endsWith(`/cases/7/analyses/${analysisId}`)) return Promise.resolve(jsonResponse({ analysis_id: analysisId, case_id: 7 }));
      if (url.pathname.endsWith("/cases/7/findings")) { requests.push(url.toString()); return Promise.resolve(jsonResponse({ items: [{ finding_id: "finding-1", title: "Filtered finding", severity: "high" }], page: Number(url.searchParams.get("page")), page_size: 50, total: 51 })); }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", retryable: false }, 404));
    }));
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" search={`?analysis=${analysisId}`} navigate={vi.fn()}/>);
    expect(await screen.findByText("Filtered finding")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Filter findings"), { target: { value: "high" } });
    await waitFor(() => expect(requests.at(-1)).toContain("severity=high"));
    fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    await waitFor(() => expect(requests.at(-1)).toContain("page=2"));
    const beforeRefresh = requests.length;
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(requests.length).toBeGreaterThan(beforeRefresh));
    expect(requests.at(-1)).toContain("page=2");
    expect(requests.at(-1)).toContain("severity=high");
    expect(requests.at(-1)).toContain(`analysis_id=${analysisId}`);
    expect(screen.getByLabelText("Filter findings")).toHaveValue("high");
  });

  it("keeps existing results visible when refresh fails and retries the request directly", async () => {
    const analysisId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; let failNextFinding = false; let findingRequests = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://traceveil.test");
      if (url.pathname.endsWith("/cases/7/summary")) return Promise.resolve(jsonResponse(summary(analysisId)));
      if (url.pathname.endsWith(`/cases/7/analyses/${analysisId}`)) return Promise.resolve(jsonResponse({ analysis_id: analysisId, case_id: 7 }));
      if (url.pathname.endsWith("/cases/7/findings")) {
        findingRequests += 1;
        if (failNextFinding) { failNextFinding = false; return Promise.resolve(jsonResponse({ code: "temporary_failure", message: "Temporary backend failure.", retryable: true }, 503)); }
        return Promise.resolve(jsonResponse(page([{ finding_id: "finding-1", title: "Persisted finding", severity: "high" }])));
      }
      return Promise.resolve(jsonResponse({}, 404));
    }));
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" search={`?analysis=${analysisId}`} navigate={vi.fn()}/>);
    expect(await screen.findByText("Persisted finding")).toBeInTheDocument();
    failNextFinding = true; fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByText("Refresh failed")).toBeInTheDocument();
    expect(screen.getByText("Persisted finding")).toBeInTheDocument();
    const beforeRetry = findingRequests;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(findingRequests).toBeGreaterThan(beforeRetry));
    await waitFor(() => expect(screen.queryByText("Refresh failed")).not.toBeInTheDocument());
    expect(screen.getByText("Persisted finding")).toBeInTheDocument();
  });

  it("ignores a superseded response even when the transport does not honor abort", async () => {
    const analysisId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; let resolveOld: ((response: Response) => void) | undefined; let unfilteredRequests = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://traceveil.test");
      if (url.pathname.endsWith("/cases/7/summary")) return Promise.resolve(jsonResponse(summary(analysisId)));
      if (url.pathname.endsWith("/cases/7/findings")) {
        const severity = url.searchParams.get("severity");
        if (!severity && ++unfilteredRequests === 2) return new Promise<Response>(resolve => { resolveOld = resolve; });
        const title = severity === "new" ? "Newest result" : "Initial result";
        return Promise.resolve(jsonResponse(page([{ finding_id: severity ?? "initial", title, severity: severity ?? "low" }])));
      }
      return Promise.resolve(jsonResponse({}, 404));
    }));
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" navigate={vi.fn()}/>);
    expect(await screen.findByText("Initial result")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(resolveOld).toBeDefined());
    fireEvent.change(screen.getByLabelText("Filter findings"), { target: { value: "new" } });
    expect(await screen.findByText("Newest result")).toBeInTheDocument();
    await act(async () => { resolveOld?.(jsonResponse(page([{ finding_id: "old", title: "Stale result", severity: "old" }]))); await Promise.resolve(); });
    expect(screen.getByText("Newest result")).toBeInTheDocument();
    expect(screen.queryByText("Stale result")).not.toBeInTheDocument();
  });

  it.each([
    ["created", "New analysis snapshot created"],
    ["reused", "Identical analysis snapshot reused"],
  ] as const)("handles a %s reanalysis on the exact Findings route", async (outcome, notice) => {
    const analysisId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; const navigate = vi.fn(); let posts = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://traceveil.test");
      if (init?.method === "POST" && url.pathname.endsWith("/cases/7/analyses")) { posts += 1; return Promise.resolve(jsonResponse({ analysis_id: analysisId, case_id: 7, status: "completed", created_at: "2026-09-02T00:00:00Z", outcome }, 202)); }
      if (url.pathname.endsWith("/cases/7/summary")) return Promise.resolve(jsonResponse(summary(analysisId)));
      if (url.pathname.endsWith(`/cases/7/analyses/${analysisId}`)) return Promise.resolve(jsonResponse({ analysis_id: analysisId, case_id: 7 }));
      if (url.pathname.endsWith("/cases/7/findings")) return Promise.resolve(jsonResponse(page([{ finding_id: "finding-1", title: posts ? "Refreshed finding" : "Existing finding", severity: "high" }])));
      return Promise.resolve(jsonResponse({}, 404));
    }));
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" search={`?analysis=${analysisId}`} navigate={navigate}/>);
    expect(await screen.findByText("Existing finding")).toBeInTheDocument();
    const control = screen.getByRole("button", { name: "Reanalyze" }); fireEvent.click(control); fireEvent.click(control);
    expect(await screen.findByText(notice)).toBeInTheDocument();
    expect(posts).toBe(1);
    expect(await screen.findByText("Refreshed finding")).toBeInTheDocument();
    expect(navigate).toHaveBeenCalledWith(`/cases/7/findings?analysis=${analysisId}`);
    expect(screen.getByRole("button", { name: "Reanalyze" })).toBeEnabled();
  });

  it("recovers from reanalysis failure without hiding current results", async () => {
    const analysisId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://traceveil.test");
      if (init?.method === "POST") return Promise.resolve(jsonResponse({ code: "temporary_failure", message: "Analysis service failed.", retryable: true }, 503));
      if (url.pathname.endsWith("/cases/7/summary")) return Promise.resolve(jsonResponse(summary(analysisId)));
      if (url.pathname.endsWith(`/cases/7/analyses/${analysisId}`)) return Promise.resolve(jsonResponse({ analysis_id: analysisId, case_id: 7 }));
      if (url.pathname.endsWith("/cases/7/findings")) return Promise.resolve(jsonResponse(page([{ finding_id: "finding-1", title: "Existing finding", severity: "high" }])));
      return Promise.resolve(jsonResponse({}, 404));
    }));
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" search={`?analysis=${analysisId}`} navigate={vi.fn()}/>);
    expect(await screen.findByText("Existing finding")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reanalyze" }));
    expect(await screen.findByText("Reanalysis failed")).toBeInTheDocument();
    expect(screen.getByText("Existing finding")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reanalyze" })).toBeEnabled();
  });

  it("uses six primary sections and opens Inspect in a dismissible detail drawer", async () => {
    respond({ "/cases/7/summary": summary("analysis-1"), "/cases/7/findings": page([{ finding_id: "finding-1", title: "Persisted finding", severity: "medium" }]) });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" navigate={vi.fn()}/>);
    const navigation = await screen.findByRole("navigation", { name: "Connected case views" });
    expect(navigation.querySelectorAll("button")).toHaveLength(6);
    fireEvent.click(screen.getByRole("button", { name: "Inspect finding-1" }));
    expect(screen.getByRole("dialog", { name: "Details for finding-1" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close record details" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Details for finding-1" })).not.toBeInTheDocument();
  });

  it("shows incidents as context within Findings instead of a separate destination", async () => {
    const incidentId = "44444444-4444-4444-8444-444444444444";
    respond({ "/cases/7/summary": summary("analysis-1"), "/cases/7/findings": page([{ finding_id: "finding-1", title: "Grouped finding", severity: "high" }]), "/cases/7/incidents": page([{ incident_id: incidentId, finding_ids: ["finding-1"], event_ids: ["event-1", "event-2"], maximum_risk: 81, correlation_edge_count: 4, started_at: "2026-09-01T00:00:00Z", ended_at: "2026-09-01T00:01:00Z" }]) });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" navigate={vi.fn()}/>);
    expect(await screen.findByText("1 incidents organize these findings")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Incidents" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: `Inspect ${incidentId}` }));
    expect(screen.getByRole("dialog", { name: `Details for ${incidentId}` })).toBeInTheDocument();
  });

  it("paginates a safely batched timeline by ten minute windows", async () => {
    const entries = Array.from({ length: 11 }, (_, index) => ({ entry_id: `event-${index + 1}`, entry_type: "event", occurred_at: `2026-09-01T00:${String(index).padStart(2, "0")}:01Z`, title: "telemetry", event_ids: [`event-${index + 1}`] }));
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://traceveil.test");
      if (url.pathname.endsWith("/cases/7/summary")) return Promise.resolve(jsonResponse(summary("analysis-1")));
      if (url.pathname.endsWith("/cases/7/charts")) return Promise.resolve(jsonResponse(page([{ series: "activity_minute", category: "2026-09-01T00:00:00Z", value: 3 }])));
      if (url.pathname.endsWith("/cases/7/timeline")) {
        const batch = url.searchParams.get("page") === "2" ? entries.slice(10) : entries.slice(0, 10);
        return Promise.resolve(jsonResponse({ items: batch, page: Number(url.searchParams.get("page")), page_size: 200, total: 201 }));
      }
      return Promise.resolve(jsonResponse({ code: "not_found", message: "Not found", retryable: false }, 404));
    }));
    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/timeline" navigate={vi.fn()}/>);
    expect(await screen.findByRole("heading", { name: "Activity across the full snapshot" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Chronological investigation timeline" }).children).toHaveLength(10);
    expect(document.querySelector(".timeline-pagination")).toHaveTextContent("Minute blocks 1–10 of 11");
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes("/cases/7/timeline?page=2&page_size=200"))).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("list", { name: "Chronological investigation timeline" }).children).toHaveLength(1);
    expect(document.querySelector(".timeline-pagination")).toHaveTextContent("Minute blocks 11–11 of 11");
    const group = screen.getByText("Review records in this minute").closest("details");
    expect(group).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Review records in this minute"));
    expect(screen.getByRole("button", { name: "Inspect event-11" })).toBeInTheDocument();
  });
});
