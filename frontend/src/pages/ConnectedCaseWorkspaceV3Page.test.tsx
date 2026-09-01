import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConnectedCaseWorkspaceV3Page } from "./ConnectedCaseWorkspaceV3Page";

const latest = {
  analysis_id: "11111111-1111-4111-8111-111111111111",
  case_id: 1,
  status: "completed",
  created_at: "2026-09-01T10:00:00Z",
  input_fingerprint: "a".repeat(64),
  input_event_count: 12,
  finding_count: 2,
  alert_count: 0,
  incident_count: 1,
  maximum_risk: 80,
  is_latest: true,
};
const historical = {
  ...latest,
  analysis_id: "22222222-2222-4222-8222-222222222222",
  created_at: "2026-08-31T10:00:00Z",
  input_fingerprint: "b".repeat(64),
  input_event_count: 10,
  is_latest: false,
};
const history = { items: [latest, historical], page: 1, page_size: 100, total: 2 };
const page = { items: [], page: 1, page_size: 50, total: 0 };
const response = (body: object, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

function installFetch(overrides?: (url: string, init?: RequestInit) => Promise<Response> | undefined) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const overridden = overrides?.(url, init);
    if (overridden) return overridden;
    if (url.includes("/analyses?page=")) return response(history);
    if (url.includes("/graph")) return response({ nodes: [], edges: [], truncated: false });
    return response(page);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("ConnectedCaseWorkspaceV3Page Step 8 workflows", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("lists persisted snapshots and navigates to a selected historical result", async () => {
    installFetch();
    const navigate = vi.fn();
    render(<ConnectedCaseWorkspaceV3Page path="/cases/1/history" search="" navigate={navigate}/>);

    expect(await screen.findByText("2 persisted analysis snapshots")).toBeInTheDocument();
    expect(screen.getByText(historical.input_fingerprint)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Review snapshot" })[1]);
    expect(navigate).toHaveBeenCalledWith(`/cases/1/findings?analysis=${historical.analysis_id}`);
  });

  it.each([
    ["findings", "/findings"],
    ["alerts", "/alerts"],
    ["incidents", "/incidents"],
    ["timeline", "/timeline"],
    ["graph", "/graph"],
    ["analytics", "/charts"],
  ])("passes the selected analysis to %s retrieval", async (section, endpoint) => {
    const fetchMock = installFetch();
    render(<ConnectedCaseWorkspaceV3Page path={`/cases/1/${section}`} search={`?analysis=${historical.analysis_id}`} navigate={vi.fn()}/>);

    await waitFor(() => expect(fetchMock.mock.calls.some(([input]) => {
      const url = String(input);
      return url.includes(endpoint) && url.includes(`analysis_id=${historical.analysis_id}`);
    })).toBe(true));
    expect(screen.getByText(`Viewing historical snapshot ${historical.analysis_id}`)).toBeInTheDocument();
  });

  it("retries the failed request directly and refreshes without route navigation", async () => {
    let findingRequests = 0;
    const fetchMock = installFetch(url => {
      if (!url.includes("/findings")) return undefined;
      findingRequests += 1;
      return findingRequests === 1 ? response({ code: "temporary", message: "Try again", retryable: true, request_id: "req-1" }, 503) : response(page);
    });
    const navigate = vi.fn();
    render(<ConnectedCaseWorkspaceV3Page path="/cases/1/findings" search="" navigate={navigate}/>);

    expect(await screen.findByRole("alert")).toHaveTextContent("Try again");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No findings")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(findingRequests).toBe(3));
    expect(navigate).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalled();
  });

  it("disables refresh while a repeated request is active", async () => {
    let resolveFindings: ((value: Response) => void) | undefined;
    let findingRequests = 0;
    installFetch(url => {
      if (!url.includes("/findings")) return undefined;
      findingRequests += 1;
      if (findingRequests === 1) return response(page);
      return new Promise<Response>(resolve => { resolveFindings = resolve; });
    });
    render(<ConnectedCaseWorkspaceV3Page path="/cases/1/findings" search="" navigate={vi.fn()}/>);
    await screen.findByText("No findings");

    const refresh = screen.getByRole("button", { name: "Refresh" });
    fireEvent.click(refresh);
    await waitFor(() => expect(refresh).toBeDisabled());
    fireEvent.click(refresh);
    expect(findingRequests).toBe(2);
    resolveFindings?.(new Response(JSON.stringify(page), { status: 200, headers: { "Content-Type": "application/json" } }));
    await waitFor(() => expect(refresh).toBeEnabled());
  });

  it("does not render stale page data as a graph while navigating between sections", async () => {
    installFetch();
    const navigate = vi.fn();
    const view = render(<ConnectedCaseWorkspaceV3Page path="/cases/1/timeline" search="" navigate={navigate}/>);
    await screen.findByText("No timeline");

    view.rerender(<ConnectedCaseWorkspaceV3Page path="/cases/1/graph" search="" navigate={navigate}/>);
    expect(await screen.findByText("Nodes")).toBeInTheDocument();
    expect(screen.getByText("Edges")).toBeInTheDocument();
  });

  it.each(["overview", "history", "evidence", "events", "findings", "alerts", "incidents", "timeline", "graph", "analytics", "reports"])("reanalyzes safely from %s and selects an idempotent result", async section => {
    let resolveReanalysis: ((value: Response) => void) | undefined;
    installFetch((url, init) => {
      if (url.endsWith("/analyses") && init?.method === "POST") return new Promise<Response>(resolve => { resolveReanalysis = resolve; });
      return undefined;
    });
    const navigate = vi.fn();
    render(<ConnectedCaseWorkspaceV3Page path={`/cases/1/${section}`} search="" navigate={navigate}/>);

    const control = screen.getByRole("button", { name: "Reanalyze" });
    fireEvent.click(control);
    expect(await screen.findByText("Reanalysis running")).toBeInTheDocument();
    expect(control).toBeDisabled();
    resolveReanalysis?.(new Response(JSON.stringify({ ...latest, reused_existing: true }), { status: 202, headers: { "Content-Type": "application/json" } }));
    expect(await screen.findByText("Unchanged inputs matched an existing snapshot; that snapshot is now selected.")).toBeInTheDocument();
    expect(navigate).toHaveBeenCalledWith(`/cases/1/findings?analysis=${latest.analysis_id}`);
  });
});
