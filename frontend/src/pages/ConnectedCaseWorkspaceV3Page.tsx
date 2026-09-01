import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { normalizeApiError } from "../api/client";
import {
  investigationApi,
  type AlertPage,
  type AnalysisHistoryPage,
  type AnalysisResult,
  type CaseSummary,
  type ChartPage,
  type EventPage,
  type EvidencePage,
  type FindingPage,
  type GraphResult,
  type IncidentPage,
  type InvestigationRecord,
  type InvestigationResponse,
  type TimelinePage,
} from "../api/investigation";
import { Button, MetricCard, PageHeader } from "../components/ui/core";
import { ConnectedReportsPanel } from "./ConnectedReportsPanel";

type PageResult = EvidencePage | EventPage | FindingPage | AlertPage | IncidentPage | TimelinePage | ChartPage;
type ReanalysisState = "idle" | "running" | "success" | "failed";

const names: Record<string, string> = { overview: "Case overview", history: "Analysis history", evidence: "Evidence", events: "Canonical events", findings: "Findings", alerts: "Alerts", incidents: "Incidents", timeline: "Timeline", graph: "Entity graph", aggregates: "Analytics", reports: "Reports", audit: "Audit history" };
const columns: Record<string, string[]> = { evidence: ["evidence_id", "original_filename", "source_type", "sha256", "received_at"], events: ["event_id", "observed_at", "event_type", "source_label", "provenance"], findings: ["finding_id", "title", "severity", "confidence", "risk"], alerts: ["alert_id", "title", "severity", "risk_score", "triggered_at"], incidents: ["incident_id", "started_at", "ended_at", "maximum_risk", "finding_ids"], timeline: ["entry_id", "occurred_at", "entry_type", "title", "severity"], aggregates: ["series", "category", "value", "subgroup"] };
const analyticalSections = new Set(["findings", "alerts", "incidents", "timeline", "graph", "aggregates"]);
const pageSections = new Set(["evidence", "events", "findings", "alerts", "incidents", "timeline", "aggregates"]);

const text = (value: object[keyof object] | string | number | boolean | null | undefined) => value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
const heading = (value: string) => value.replaceAll("_", " ");
const isPageResult = (value: InvestigationResponse): value is PageResult => "items" in value && "total" in value;

export function ConnectedCaseWorkspaceV3Page({ path, search, navigate }: { path: string; search: string; navigate: (path: string) => void }) {
  const [, , id = "", requested = "overview"] = path.split("/");
  const caseId = Number(id);
  const section = requested === "analytics" ? "aggregates" : requested;
  const selectedAnalysisId = useMemo(() => new URLSearchParams(search).get("analysis"), [search]);
  const [data, setData] = useState<InvestigationResponse | null>(null);
  const [dataKey, setDataKey] = useState<string | null>(null);
  const [history, setHistory] = useState<AnalysisHistoryPage | null>(null);
  const [loading, setLoading] = useState(section !== "reports");
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [pageNumber, setPageNumber] = useState(1);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [reanalysisState, setReanalysisState] = useState<ReanalysisState>("idle");
  const [reanalysisMessage, setReanalysisMessage] = useState<string | null>(null);
  const requestSequence = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const reanalysisRequest = useRef<AbortController | null>(null);

  const filters = useMemo(() => ({
    page: pageNumber,
    pageSize: 50,
    source: section === "evidence" ? query || undefined : undefined,
    eventType: section === "events" ? query || undefined : undefined,
    severity: ["findings", "alerts", "incidents", "timeline"].includes(section) ? query || undefined : undefined,
    analysisId: analyticalSections.has(section) ? selectedAnalysisId : null,
  }), [pageNumber, query, section, selectedAnalysisId]);
  const requestKey = useMemo(
    () => JSON.stringify({ caseId, section, selectedAnalysisId, filters }),
    [caseId, filters, section, selectedAnalysisId],
  );

  const requestSection = useCallback((signal: AbortSignal): Promise<InvestigationResponse> => {
    if (section === "overview") return selectedAnalysisId ? investigationApi.analysis(caseId, selectedAnalysisId, signal) : investigationApi.summary(caseId, signal);
    if (section === "history") return investigationApi.history(caseId, signal);
    if (section === "evidence") return investigationApi.evidence(caseId, filters, signal);
    if (section === "events") return investigationApi.events(caseId, filters, signal);
    if (section === "findings") return investigationApi.findings(caseId, filters, signal);
    if (section === "alerts") return investigationApi.alerts(caseId, filters, signal);
    if (section === "incidents") return investigationApi.incidents(caseId, filters, signal);
    if (section === "timeline") return investigationApi.timeline(caseId, filters, signal);
    if (section === "graph") return investigationApi.graph(caseId, selectedAnalysisId, signal);
    if (section === "aggregates") return investigationApi.charts(caseId, selectedAnalysisId, signal);
    return investigationApi.summary(caseId, signal);
  }, [caseId, filters, section, selectedAnalysisId]);

  const load = useCallback(async () => {
    if (section === "reports") { setLoading(false); setError(null); return; }
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const sequence = ++requestSequence.current;
    setLoading(true);
    setError(null);
    try {
      const nextHistory = await investigationApi.history(caseId, controller.signal);
      if (selectedAnalysisId && !nextHistory.items.some(item => item.analysis_id === selectedAnalysisId)) throw new Error("The selected analysis snapshot is not available for this case.");
      const nextData = section === "history" ? nextHistory : await requestSection(controller.signal);
      if (sequence === requestSequence.current) { setHistory(nextHistory); setData(nextData); setDataKey(requestKey); }
    } catch (reason) {
      if (!controller.signal.aborted && sequence === requestSequence.current) setError(normalizeApiError(reason).message);
    } finally {
      if (!controller.signal.aborted && sequence === requestSequence.current) setLoading(false);
    }
  }, [caseId, requestKey, requestSection, section, selectedAnalysisId, refreshVersion]);

  useEffect(() => { setPageNumber(1); }, [section]);
  useEffect(() => { void load(); return () => activeRequest.current?.abort(); }, [load]);
  useEffect(() => () => reanalysisRequest.current?.abort(), []);

  const snapshotSuffix = (analysisId = selectedAnalysisId) => analysisId ? `?analysis=${encodeURIComponent(analysisId)}` : "";
  const navigateSection = (nextSection: string, analysisId = selectedAnalysisId) => navigate(`/cases/${id}/${nextSection}${snapshotSuffix(analysisId)}`);
  const refresh = () => { setLoading(true); setRefreshVersion(value => value + 1); };
  const selectedSnapshot = history?.items.find(item => item.analysis_id === selectedAnalysisId) ?? null;

  const reanalyze = async () => {
    if (reanalysisState === "running") return;
    reanalysisRequest.current?.abort();
    const controller = new AbortController();
    reanalysisRequest.current = controller;
    setReanalysisState("running");
    setReanalysisMessage("Deterministic reanalysis is running against persisted events.");
    try {
      const result = await investigationApi.reanalyze(caseId, controller.signal);
      setReanalysisState("success");
      setReanalysisMessage(result.reused_existing ? "Unchanged inputs matched an existing snapshot; that snapshot is now selected." : "Reanalysis completed and the new snapshot is now selected.");
      navigateSection("findings", result.analysis_id);
      setRefreshVersion(value => value + 1);
    } catch (reason) {
      if (!controller.signal.aborted) { setReanalysisState("failed"); setReanalysisMessage(normalizeApiError(reason).message); }
    }
  };

  const currentData = dataKey === requestKey ? data : null;
  const viewLoading = section !== "reports" && !error && (loading || dataKey !== requestKey);
  const page = currentData && isPageResult(currentData) ? currentData : null;
  const graph = section === "graph" && currentData ? currentData as GraphResult : null;
  const overview = section === "overview" && currentData ? currentData as CaseSummary | AnalysisResult : null;
  const historyData = section === "history" && currentData ? currentData as AnalysisHistoryPage : null;
  const items = page?.items ?? [];

  return <>
    <PageHeader
      eyebrow={`Persisted batch investigation · CASE-${id.padStart(4, "0")}`}
      title={names[section] ?? heading(section)}
      description="Connected records preserve backend IDs, UTC timestamps, nulls, provenance, rule traces, risk factors, and supporting evidence identifiers."
      actions={<><Button onClick={() => navigate("/import")}>Import evidence</Button><Button onClick={refresh} disabled={viewLoading}>Refresh</Button><Button variant="primary" onClick={reanalyze} disabled={reanalysisState === "running"}>{reanalysisState === "running" ? "Reanalyzing…" : "Reanalyze"}</Button></>}
    />
    <div className="filter-row" aria-label="Analysis context">
      <label htmlFor="analysis-snapshot"><b>Analysis snapshot</b></label>
      <select id="analysis-snapshot" className="input" value={selectedAnalysisId ?? ""} onChange={event => navigateSection(requested, event.target.value || null)}>
        <option value="">Latest analysis</option>
        {history?.items.map(item => <option key={item.analysis_id} value={item.analysis_id}>{item.is_latest ? "Latest" : "Historical"} · {item.created_at} · {item.analysis_id.slice(0, 8)}</option>)}
      </select>
      <span>{selectedSnapshot ? selectedSnapshot.is_latest ? "Explicitly viewing the latest persisted snapshot" : `Viewing historical snapshot ${selectedSnapshot.analysis_id}` : "Following the latest persisted analysis"}</span>
    </div>
    <nav className="case-tabs" aria-label="Connected case views">{["overview", "history", "evidence", "events", "findings", "alerts", "incidents", "timeline", "graph", "analytics", "reports"].map(tab => <button className={requested === tab ? "active" : ""} onClick={() => navigateSection(tab)} key={tab}>{tab === "history" ? "Analysis history" : tab}</button>)}</nav>
    {reanalysisMessage && <div className="settings-notice" role={reanalysisState === "failed" ? "alert" : "status"}><div><b>{reanalysisState === "running" ? "Reanalysis running" : reanalysisState === "failed" ? "Reanalysis failed" : "Reanalysis complete"}</b><p>{reanalysisMessage}</p></div></div>}
    {viewLoading && <div className="state-box" aria-live="polite"><strong>Loading persisted {heading(section)}…</strong></div>}
    {error && <div className="state-box" role="alert"><strong>{selectedAnalysisId ? "Selected snapshot unavailable" : "Connected view unavailable"}</strong><p>{error}</p><Button onClick={refresh} disabled={viewLoading}>Retry</Button></div>}
    {!viewLoading && !error && section === "reports" && <ConnectedReportsPanel caseId={caseId}/>}
    {!viewLoading && !error && section === "history" && historyData && <HistoryTable history={historyData} selectedAnalysisId={selectedAnalysisId} onReview={analysisId => navigateSection("findings", analysisId)}/>}
    {!viewLoading && !error && section === "overview" && overview && <div className="metrics-grid">{Object.entries(overview).filter(([, value]) => value == null || ["string", "number", "boolean"].includes(typeof value)).map(([key, value]) => <MetricCard key={key} label={heading(key)} value={text(value)} detail={key.includes("time") || key.endsWith("_at") ? "UTC" : selectedAnalysisId ? "Historical snapshot" : "Backend value"}/>)}</div>}
    {!viewLoading && !error && section === "graph" && graph && <section className="table-panel">{graph.truncated && <div className="settings-notice" role="status"><div><b>Partial graph</b><p>The backend applied node or edge safety limits. Refine the case scope before drawing conclusions.</p></div></div>}<div className="metrics-grid"><MetricCard label="Nodes" value={graph.nodes.length}/><MetricCard label="Edges" value={graph.edges.length}/><MetricCard label="Truncated" value={graph.truncated ? "Yes" : "No"}/></div><RecordTable section="graph nodes" items={graph.nodes}/><RecordTable section="graph edges" items={graph.edges}/></section>}
    {!viewLoading && !error && pageSections.has(section) && page && <section className="table-panel"><div className="filter-row"><input className="input" aria-label={`Filter ${section}`} placeholder={section === "events" ? "Exact event type" : section === "evidence" ? "Exact source" : ["findings", "alerts", "incidents", "timeline"].includes(section) ? "Exact severity" : `Filter ${section}`} value={query} onChange={event => { setQuery(event.target.value); setPageNumber(1); }}/><span>{page.total} persisted records</span></div><RecordTable section={section} items={items} columns={columns[section]} filtered={Boolean(query)}/>{page.total > 50 && <div className="table-footer"><Button disabled={pageNumber === 1} onClick={() => setPageNumber(value => value - 1)}>Previous</Button><span>Page {pageNumber}</span><Button disabled={pageNumber * 50 >= page.total} onClick={() => setPageNumber(value => value + 1)}>Next</Button></div>}</section>}
  </>;
}

function HistoryTable({ history, selectedAnalysisId, onReview }: { history: AnalysisHistoryPage; selectedAnalysisId: string | null; onReview: (analysisId: string) => void }) {
  if (!history.items.length) return <div className="state-box"><strong>No analysis snapshots</strong><p>Import and commit evidence before reviewing historical analysis.</p></div>;
  return <section className="table-panel"><div className="table-footer"><span>{history.total} persisted analysis snapshots</span></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Context</th><th>Analysis ID</th><th>Created (UTC)</th><th>Status</th><th>Input fingerprint</th><th>Events</th><th>Findings</th><th>Incidents</th><th/></tr></thead><tbody>{history.items.map(item => <tr key={item.analysis_id} aria-current={item.analysis_id === selectedAnalysisId ? "true" : undefined}><td>{item.is_latest ? "Latest" : "Historical"}</td><td><code>{item.analysis_id}</code></td><td>{item.created_at}</td><td>{item.status}</td><td><code>{item.input_fingerprint}</code></td><td>{item.input_event_count}</td><td>{item.finding_count}</td><td>{item.incident_count}</td><td><Button onClick={() => onReview(item.analysis_id)}>Review snapshot</Button></td></tr>)}</tbody></table></div></section>;
}

function RecordTable({ section, items, columns: requested, filtered = false }: { section: string; items: InvestigationRecord[]; columns?: string[]; filtered?: boolean }) {
  if (!items.length) return <div className="state-box"><strong>{filtered ? `No ${section} match this filter` : `No ${section}`}</strong><p>{filtered ? "The backend returned no records for the active filter." : "The backend returned no records for this analysis context."}</p></div>;
  const entries = items.map(item => Object.entries(item));
  const visible = requested?.filter(column => entries.some(record => record.some(([key]) => key === column))) ?? entries[0].filter(([, value]) => typeof value !== "object").map(([key]) => key).slice(0, 6);
  return <div className="data-table-wrap"><table className="data-table"><thead><tr>{visible.map(column => <th key={column}>{heading(column)}</th>)}<th>Details</th></tr></thead><tbody>{items.map((item, index) => { const record = entries[index]; const identifier = record.find(([key]) => ["evidence_id", "event_id", "finding_id", "alert_id", "incident_id", "entry_id", "node_id", "edge_id"].includes(key))?.[1]; return <tr key={identifier == null ? `${section}-${index}` : String(identifier)}>{visible.map(column => <td key={column}>{text(record.find(([key]) => key === column)?.[1])}</td>)}<td><details><summary>Inspect</summary><dl className="record-details">{record.map(([key, value]) => <div key={key}><dt>{heading(key)}</dt><dd>{text(value)}</dd></div>)}</dl></details></td></tr>; })}</tbody></table></div>;
}
