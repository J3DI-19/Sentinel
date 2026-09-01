import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConnectedCaseWorkspaceV3Page } from "./ConnectedCaseWorkspaceV3Page";

const summary = (analysisId: string | null) => ({ case: { id: 7, name: "Case Seven" }, event_count: 2, entity_count: 1, finding_count: 0, alert_count: 0, incident_count: 0, maximum_risk: 0, analysis_id: analysisId });
const page = (items: Record<string, unknown>[]) => ({ items, page: 1, page_size: 50, total: items.length });
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

    respond({ "/cases/7/summary": summary("analysis-1"), "/cases/7/evidence": page([{ evidence_id: evidenceId, original_name: "visible.csv" }]) });
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
    fireEvent.click(screen.getByRole("button", { name: "incidents" }));
    expect(navigate).toHaveBeenCalledWith(`/cases/7/incidents?analysis=${historicalId}`);
  });

  it("loads historical chart data and rejects malformed snapshot IDs", async () => {
    const latestId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"; const historicalId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
    respond({ "/cases/7/summary": summary(latestId), "/cases/7/charts": page([{ series: "event_type", category: "motion", value: 2 }]), [`/cases/7/analyses/${historicalId}`]: { analysis_id: historicalId, case_id: 7 } });
    const { unmount } = render(<ConnectedCaseWorkspaceV3Page path="/cases/7/charts" search={`?analysis=${historicalId}`} navigate={vi.fn()}/>);
    expect(await screen.findByText("motion")).toBeInTheDocument();
    expect(vi.mocked(fetch).mock.calls.some(([input]) => String(input).includes(`/cases/7/charts?analysis_id=${historicalId}`))).toBe(true); unmount();

    render(<ConnectedCaseWorkspaceV3Page path="/cases/7/findings" search="?analysis=invalid" navigate={vi.fn()}/>);
    expect(await screen.findByText("Selected analysis unavailable")).toBeInTheDocument();
    expect(screen.getByText(/selected analysis ID is malformed/i)).toBeInTheDocument();
  });
});
