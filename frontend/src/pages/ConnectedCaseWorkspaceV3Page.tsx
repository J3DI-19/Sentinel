import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "../api/batch";
import { phase3Api } from "../api/phase3";
import { normalizeApiError, serializeQuery } from "../api/client";
import { Button, MetricCard, PageHeader } from "../components/ui/core";
import { ConnectedReportsPanel } from "./ConnectedReportsPanel";
import { mapInvestigationRecords, type InvestigationRecordKind, type InvestigationRecordViewModel } from "../features/investigation/viewModels";
import { IncidentContext, PersistedTimeline, PersistedVisuals, TimelineActivityOverview } from "../features/investigation/PersistedVisuals";
import type { components } from "../api/generated";

interface PageResult { items?: Record<string, unknown>[]; page?: number; page_size?: number; total?: number }
interface CaseSummary { analysis_id?: string | null; event_count?: number; [key: string]: unknown }
interface AnalysisSnapshot { analysis_id: string; case_id: number; status: string; created_at: string }
type ReanalysisResult = components["schemas"]["ReanalysisPublic"];
type LoadMode = "initial" | "refresh";
const names: Record<string, string> = { overview: "Case overview", evidence: "Evidence", events: "Canonical events", history: "Analysis history", findings: "Findings", alerts: "Alerts", incidents: "Incidents", timeline: "Timeline", visuals: "Visuals", reports: "Reports", audit: "Audit history" };
const columns: Record<string, string[]> = {
  evidence: ["evidence_id", "original_filename", "source_type", "validation_status", "sha256", "received_at"],
  events: ["event_id", "observed_at", "origin", "event_type", "entity_id"],
  findings: ["finding_id", "title", "severity", "risk_score", "rule_id"],
  alerts: ["alert_id", "title", "severity", "risk_score", "triggered_at"],
  incidents: ["incident_id", "maximum_risk", "correlation_edge_count", "correlation_edges_truncated", "started_at", "ended_at"],
  timeline: ["entry_id", "occurred_at", "entry_type", "title", "severity", "risk_score"],
  audit: ["occurred_at", "action", "actor", "subject_type", "subject_id", "request_id"],
  aggregates: ["series", "category", "subgroup", "value"],
  charts: ["series", "category", "subgroup", "value"],
  "graph nodes": ["node_id", "kind", "label", "event_count", "maximum_risk"],
  "graph edges": ["edge_id", "source_node_id", "target_node_id", "relationships", "event_count"],
};
const analysisSections = new Set(["findings", "alerts", "incidents", "timeline", "visuals"]);
const visualAliases = new Set(["graph", "charts", "aggregates", "analytics"]);
const primaryTabs = ["overview", "evidence", "findings", "timeline", "visuals", "reports"];
const timelineBatchSize = 200;
const timelineWindowsPerPage = 10;
const heading = (value: string) => value.replaceAll("_", " ");
const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const display = (value: unknown): string => value == null ? "—" : typeof value === "boolean" ? (value ? "Yes" : "No") : Array.isArray(value) ? value.join(", ") : typeof value === "object" ? "Structured details" : String(value);
const valueFor = (item: Record<string, unknown>, column: string): unknown => column === "risk_score" ? item.risk_score ?? item.score ?? record(item.risk).score : item[column];
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
async function loadCompleteTimeline(caseId: string, analysisId: string | null, signal: AbortSignal): Promise<PageResult> {
  const path = (page: number) => `/cases/${caseId}/timeline${serializeQuery({ page, page_size: timelineBatchSize, analysis_id: analysisId })}`;
  const first = await apiClient.request<PageResult>(path(1), { signal });
  const total = first.total ?? first.items?.length ?? 0;
  const pages = Math.ceil(total / timelineBatchSize);
  const items = [...(first.items ?? [])];
  for (let page = 2; page <= pages; page += 1) {
    const result = await apiClient.request<PageResult>(path(page), { signal });
    items.push(...(result.items ?? []));
  }
  return { ...first, items, page: 1, page_size: items.length, total };
}

export function ConnectedCaseWorkspaceV3Page({ path, search = "", navigate }: { path: string; search?: string; navigate: (path: string) => void }) {
  const [, , id = "", requested = "overview"] = path.split("/"); const caseId = Number(id); const section = requested === "incidents" ? "findings" : visualAliases.has(requested) ? "visuals" : requested;
  const requestedAnalysis = new URLSearchParams(search).get("analysis");
  const selectedAnalysisId = requestedAnalysis && uuid.test(requestedAnalysis) ? requestedAnalysis : null;
  const snapshotSearch = selectedAnalysisId ? serializeQuery({ analysis: selectedAnalysisId }) : "";
  const [data, setData] = useState<unknown>(null); const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [loading, setLoading] = useState(section !== "reports"); const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null); const [refreshError, setRefreshError] = useState<string | null>(null);
  const [query, setQuery] = useState(""); const [pageNumber, setPageNumber] = useState(1); const [reportRefresh, setReportRefresh] = useState(0);
  const [selected, setSelected] = useState<InvestigationRecordViewModel | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [relatedIncidents, setRelatedIncidents] = useState<Record<string, unknown>[]>([]);
  const [timelinePoints, setTimelinePoints] = useState<Record<string, unknown>[]>([]);
  const [referenceError, setReferenceError] = useState<string | null>(null); const [resolvingReference, setResolvingReference] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false); const [reanalysisError, setReanalysisError] = useState<string | null>(null);
  const [reanalysisResult, setReanalysisResult] = useState<ReanalysisResult | null>(null);
  const loadSequence = useRef(0); const activeLoad = useRef<AbortController | null>(null); const refreshFlight = useRef(false); const reanalysisFlight = useRef(false);
  const pageSize = section === "history" ? 25 : 50;
  const requestPageNumber = section === "timeline" ? 1 : pageNumber;
  const endpoint = useMemo(() => {
    if (section === "overview") return `/cases/${id}/summary`;
    if (section === "history") return `/cases/${id}/analyses${serializeQuery({ page: pageNumber, page_size: 25 })}`;
    if (section === "visuals") return `/cases/${id}/charts${serializeQuery({ analysis_id: selectedAnalysisId })}`;
    const filter = section === "events" ? { event_type: query || undefined } : section === "evidence" ? { source: query || undefined } : ["findings", "alerts", "incidents", "timeline"].includes(section) ? { severity: query || undefined } : {};
    return `/cases/${id}/${section}${serializeQuery({ page: requestPageNumber, page_size: section === "timeline" ? timelineBatchSize : pageSize, ...filter, analysis_id: analysisSections.has(section) ? selectedAnalysisId : null })}`;
  }, [id, pageSize, query, requestPageNumber, section, selectedAnalysisId]);

  useEffect(() => { setPageNumber(1); setQuery(""); setSelected(null); setDetailOpen(false); setReferenceError(null); }, [section]);
  useEffect(() => { setPageNumber(1); setSelected(null); }, [selectedAnalysisId]);

  const loadWorkspace = useCallback((mode: LoadMode) => {
    if (requestedAnalysis && !selectedAnalysisId) {
      activeLoad.current?.abort(); loadSequence.current += 1; refreshFlight.current = false;
      setLoading(false); setRefreshing(false); setRefreshError(null);
      setError("The selected analysis ID is malformed. Open Analysis history and choose a persisted snapshot.");
      return null;
    }
    const requestId = ++loadSequence.current; activeLoad.current?.abort();
    const controller = new AbortController(); activeLoad.current = controller;
    if (mode === "initial") { refreshFlight.current = false; setRefreshing(false); setLoading(true); } else setRefreshing(true);
    setError(null); setRefreshError(null);
    const summaryRequest = apiClient.request<CaseSummary>(`/cases/${id}/summary`, { signal: controller.signal });
    const dataRequest: Promise<unknown> = section === "reports" ? Promise.resolve(null) : section === "audit" ? phase3Api.audit(caseId, controller.signal) : section === "overview" ? summaryRequest : section === "timeline" ? loadCompleteTimeline(id, selectedAnalysisId, controller.signal) : section === "visuals" ? Promise.all([
      apiClient.request<unknown>(`/cases/${id}/charts${serializeQuery({ analysis_id: selectedAnalysisId })}`, { signal: controller.signal }),
      apiClient.request<unknown>(`/cases/${id}/graph${serializeQuery({ analysis_id: selectedAnalysisId })}`, { signal: controller.signal }),
    ]).then(([charts, graph]) => ({ charts, graph })) : apiClient.request<unknown>(endpoint, { signal: controller.signal });
    const snapshotRequest = selectedAnalysisId ? apiClient.request(`/cases/${id}/analyses/${selectedAnalysisId}`, { signal: controller.signal }) : Promise.resolve(null);
    const contextRequest = section === "findings"
      ? apiClient.request<PageResult>(`/cases/${id}/incidents${serializeQuery({ page: 1, page_size: 50, analysis_id: selectedAnalysisId })}`, { signal: controller.signal }).catch(() => null)
      : section === "timeline"
      ? apiClient.request<PageResult>(`/cases/${id}/charts${serializeQuery({ analysis_id: selectedAnalysisId })}`, { signal: controller.signal }).catch(() => null)
      : Promise.resolve(null);
    void Promise.all([summaryRequest, dataRequest, snapshotRequest, contextRequest]).then(([nextSummary, nextData, , contextData]) => {
      if (controller.signal.aborted || requestId !== loadSequence.current) return;
      setSummary(nextSummary); setData(section === "overview" ? nextSummary : nextData);
      setRelatedIncidents(section === "findings" && contextData?.items ? contextData.items : []);
      setTimelinePoints(section === "timeline" && contextData?.items ? contextData.items : []);
    }).catch(reason => {
      if (controller.signal.aborted || requestId !== loadSequence.current) return;
      const message = normalizeApiError(reason).message;
      if (mode === "initial") setError(message); else setRefreshError(message);
    }).finally(() => {
      if (requestId !== loadSequence.current) return;
      if (activeLoad.current === controller) activeLoad.current = null;
      if (mode === "initial") setLoading(false); else { setRefreshing(false); refreshFlight.current = false; }
    });
    return controller;
  }, [caseId, endpoint, id, requestedAnalysis, section, selectedAnalysisId]);

  useEffect(() => { const controller = loadWorkspace("initial"); return () => controller?.abort(); }, [loadWorkspace]);

  const refreshWorkspace = () => {
    if (refreshFlight.current) return;
    refreshFlight.current = true;
    if (section === "reports") setReportRefresh(value => value + 1);
    if (!loadWorkspace("refresh")) refreshFlight.current = false;
  };

  const reanalyze = async () => {
    if (reanalysisFlight.current) return;
    reanalysisFlight.current = true; setReanalyzing(true); setReanalysisError(null); setReanalysisResult(null);
    try {
      const result = await apiClient.request<ReanalysisResult>(`/cases/${id}/analyses`, { method: "POST" });
      setReanalysisResult(result);
      const target = `/cases/${id}/findings${serializeQuery({ analysis: result.analysis_id })}`;
      const alreadyShowingResult = `${path}${search}` === target;
      navigate(target);
      if (alreadyShowingResult) { refreshFlight.current = true; loadWorkspace("refresh"); }
    } catch (reason) {
      setReanalysisError(normalizeApiError(reason).message);
    } finally {
      reanalysisFlight.current = false; setReanalyzing(false);
    }
  };

  const object = record(data); const result = object as PageResult; const all = Array.isArray(result.items) ? result.items : [];
  const mapped = mapInvestigationRecords(section as InvestigationRecordKind, all);
  useEffect(() => {
    if (loading || error || !["evidence", "events"].includes(section)) return;
    const parameter = section === "evidence" ? "evidence" : "event"; const requestedId = new URLSearchParams(search).get(parameter);
    if (!requestedId) { setReferenceError(null); setSelected(null); setDetailOpen(false); return; }
    if (!uuid.test(requestedId)) { setSelected(null); setDetailOpen(false); setReferenceError(`The requested ${parameter} reference is malformed.`); return; }
    const existing = mapped.find(item => item.id === requestedId);
    if (existing) { setSelected(existing); setDetailOpen(true); setReferenceError(null); return; }
    const controller = new AbortController(); setResolvingReference(true); setReferenceError(null);
    const detailPath = section === "evidence" ? `/cases/${id}/evidence/${requestedId}` : `/cases/${id}/events/${requestedId}`;
    void apiClient.request<Record<string, unknown>>(detailPath, { signal: controller.signal }).then(value => { setSelected(mapInvestigationRecords(section as InvestigationRecordKind, [value])[0]); setDetailOpen(true); }).catch(() => { if (!controller.signal.aborted) { setSelected(null); setDetailOpen(false); setReferenceError(`The requested ${parameter} is unavailable or does not belong to this case.`); } }).finally(() => { if (!controller.signal.aborted) setResolvingReference(false); });
    return () => controller.abort();
  }, [data, error, id, loading, search, section]);

  const selectRecord = (item: InvestigationRecordViewModel) => { const analysis = selectedAnalysisId ?? undefined; setSelected(item); setDetailOpen(true); if (section === "evidence") navigate(`/cases/${id}/evidence${serializeQuery({ evidence: item.id, analysis })}`); else if (section === "events") navigate(`/cases/${id}/events${serializeQuery({ event: item.id, analysis })}`); };
  const total = result.total ?? all.length; const start = total ? (pageNumber - 1) * pageSize + 1 : 0; const end = Math.min(pageNumber * pageSize, total);
  const viewingHistorical = Boolean(selectedAnalysisId && summary?.analysis_id !== selectedAnalysisId);
  const snapshotLabel = viewingHistorical ? "historical analysis" : "latest analysis";

  const primarySection = section === "events" ? "evidence" : section === "alerts" ? "findings" : section === "audit" ? "reports" : section;
  const visualData = record(data); const chartResult = record(visualData.charts) as PageResult; const graphResult = record(visualData.graph) as { nodes?: Record<string, unknown>[]; edges?: Record<string, unknown>[]; truncated?: boolean };
  return <><PageHeader eyebrow={`Persisted investigation · CASE-${id.padStart(4, "0")}`} title={names[section] ?? heading(section)} description="Connected records and visual summaries preserve backend-authored identifiers, timestamps, provenance, rule traces, and risk factors." actions={<><Button onClick={() => navigate(`/cases/${id}/history${snapshotSearch}`)}>Analysis history</Button><Button disabled={loading || refreshing} onClick={refreshWorkspace}>{refreshing ? "Refreshing…" : "Refresh"}</Button><Button onClick={() => navigate(`/import?case=${id}`)}>Import evidence</Button><Button variant="primary" disabled={reanalyzing} onClick={reanalyze}>{reanalyzing ? "Reanalyzing…" : "Reanalyze"}</Button></>}/>
    <nav className="case-tabs case-tabs-primary" aria-label="Connected case views">{primaryTabs.map(tab => <button className={primarySection === tab ? "active" : ""} onClick={() => navigate(`/cases/${id}/${tab}${snapshotSearch}`)} key={tab}>{tab}</button>)}</nav>
    {(["evidence", "events"].includes(section) || ["findings", "alerts"].includes(section) || ["reports", "audit"].includes(section)) && <nav className="case-subtabs" aria-label={`${primarySection} views`}>{(primarySection === "evidence" ? [["evidence", "Imported evidence"], ["events", "Canonical events"]] : primarySection === "findings" ? [["findings", "Findings & incidents"], ["alerts", "Alerts"]] : [["reports", "Reports"], ["audit", "Audit history"]]).map(([tab, label]) => <button className={section === tab ? "active" : ""} onClick={() => navigate(`/cases/${id}/${tab}${snapshotSearch}`)} key={tab}>{label}</button>)}</nav>}
    {refreshing && <div className="settings-notice" role="status"><div><b>Refreshing persisted data</b><p>The current view remains available while Traceveil reloads this case.</p></div></div>}
    {refreshError && <div className="settings-notice reference-warning" role="alert"><div><b>Refresh failed</b><p>{refreshError} Existing results remain available.</p></div><Button disabled={refreshing} onClick={refreshWorkspace}>Retry</Button></div>}
    {reanalysisError && <div className="settings-notice reference-warning" role="alert"><div><b>Reanalysis failed</b><p>{reanalysisError} Existing persisted results were not replaced.</p></div><Button disabled={reanalyzing} onClick={reanalyze}>Retry reanalysis</Button></div>}
    {reanalysisResult && <div className="settings-notice" role="status"><div><b>{reanalysisResult.outcome === "created" ? "New analysis snapshot created" : "Identical analysis snapshot reused"}</b><p>{reanalysisResult.outcome === "created" ? "Traceveil persisted a new deterministic result." : "The evidence and analysis inputs were unchanged, so Traceveil reused the existing deterministic result."} Snapshot <code>{reanalysisResult.analysis_id}</code>.</p></div></div>}
    {loading && <div className="state-box" aria-live="polite"><strong>Loading persisted {heading(section)}…</strong><p>Traceveil is reading case-owned records from the backend.</p></div>}
    {error && <div className="state-box" role="alert"><strong>{requestedAnalysis ? "Selected analysis unavailable" : "Connected view unavailable"}</strong><p>{error}</p>{requestedAnalysis ? <Button onClick={() => navigate(`/cases/${id}/history`)}>Open analysis history</Button> : <Button onClick={() => loadWorkspace("initial")}>Retry</Button>}</div>}
    {!loading && !error && summary?.analysis_id && (analysisSections.has(section) || section === "history") && <div className={`analysis-snapshot-banner ${viewingHistorical ? "historical" : "latest"}`} role="status"><div><span>{viewingHistorical ? "Historical snapshot" : "Latest snapshot"}</span><b>{selectedAnalysisId ?? summary.analysis_id}</b><p>{viewingHistorical ? "Results are pinned to a persisted historical analysis and will stay selected across case tabs." : "Results use the case's latest persisted analysis."}</p></div>{viewingHistorical && <Button onClick={() => navigate(`/cases/${id}/${section}`)}>View latest</Button>}</div>}
    {!loading && !error && referenceError && <div className="settings-notice reference-warning" role="alert"><div><b>Source reference unavailable</b><p>{referenceError} The surrounding persisted results remain available.</p></div><Button onClick={() => navigate(`/cases/${id}/${section}${snapshotSearch}`)}>Clear reference</Button></div>}
    {!loading && !error && resolvingReference && <div className="settings-notice" role="status"><div><b>Opening source record</b><p>Resolving the case-owned reference from persisted data…</p></div></div>}
    {!loading && !error && section === "reports" && <ConnectedReportsPanel key={reportRefresh} caseId={caseId}/>}
    {!loading && !error && section === "history" && <AnalysisHistory snapshots={all as unknown as AnalysisSnapshot[]} latestId={summary?.analysis_id ?? null} selectedId={selectedAnalysisId} caseId={id} pageNumber={pageNumber} total={total} onPage={setPageNumber} navigate={navigate}/>}
    {!loading && !error && section === "overview" && <><div className="metrics-grid">{Object.entries(object).filter(([, value]) => value == null || ["string", "number", "boolean"].includes(typeof value)).map(([key, value]) => <MetricCard key={key} label={heading(key)} value={display(value)} detail={key.includes("time") || key.endsWith("_at") ? "UTC" : "Persisted backend value"}/>)}</div>{!summary?.analysis_id && <EmptyState title="No analysis has run" message="This case has no persisted analysis snapshot yet. Import evidence or run deterministic analysis to create result sections." action="Import evidence" onAction={() => navigate(`/import?case=${id}`)}/>}</>}
    {!loading && !error && section === "visuals" && (summary?.analysis_id ? <PersistedVisuals points={(chartResult.items ?? []) as { series?: string; category?: string; subgroup?: string | null; value?: number }[]} nodes={graphResult.nodes ?? []} edges={graphResult.edges ?? []} truncated={graphResult.truncated}/> : <NoAnalysis onRun={reanalyze} disabled={reanalyzing}/>)}
    {!loading && !error && section === "timeline" && (summary?.analysis_id ? <><TimelineActivityOverview points={timelinePoints} total={total}/><section className="table-panel timeline-visual-panel"><div className="filter-row timeline-window-header"><div><strong>Chronological record windows</strong><p>Each stop represents one minute. Ten minute blocks are shown per page regardless of activity density.</p></div><span>{total ? `${total.toLocaleString()} persisted entries loaded in safe batches` : "0 persisted entries"}</span></div>{all.length ? <PersistedTimeline items={all} onInspect={selectRecord} page={pageNumber} windowsPerPage={timelineWindowsPerPage} onPage={setPageNumber}/> : <SectionEmpty section={section} filtered={Boolean(query)} analyzed snapshotLabel={snapshotLabel} caseId={id} onClear={() => setQuery("")} navigate={navigate} onRun={reanalyze} runDisabled={reanalyzing}/>}</section></> : <NoAnalysis onRun={reanalyze} disabled={reanalyzing}/>)}
    {!loading && !error && section === "findings" && summary?.analysis_id && <IncidentContext items={relatedIncidents} onInspect={selectRecord}/>}
    {!loading && !error && !["overview", "history", "visuals", "timeline", "reports"].includes(section) && <section className="workspace-results"><div className="table-panel"><div className="filter-row"><input className="input" aria-label={`Filter ${section}`} placeholder={section === "events" ? "Exact event type" : section === "evidence" ? "Exact source" : ["findings", "alerts", "incidents"].includes(section) ? "Exact severity" : `Filter ${section}`} value={query} onChange={event => { setQuery(event.target.value); setPageNumber(1); }}/><span>{total ? `Showing ${start}–${end} of ${total} persisted records` : "0 persisted records"}</span></div>{all.length ? <RecordTable section={section} items={all} columns={columns[section]} selectedId={selected?.id} onSelect={selectRecord}/> : <SectionEmpty section={section} filtered={Boolean(query)} analyzed={Boolean(summary?.analysis_id)} snapshotLabel={snapshotLabel} caseId={id} onClear={() => setQuery("")} navigate={navigate} onRun={reanalyze} runDisabled={reanalyzing}/>} {total > 50 && <div className="table-footer"><Button disabled={pageNumber === 1} onClick={() => setPageNumber(value => value - 1)}>Previous</Button><span>Page {pageNumber} · partial view of {total}</span><Button disabled={pageNumber * 50 >= total} onClick={() => setPageNumber(value => value + 1)}>Next</Button></div>}</div></section>}
    {selected && detailOpen && <RecordDetail item={selected} caseId={id} analysisId={selectedAnalysisId} navigate={navigate} onClose={() => setDetailOpen(false)}/>}
  </>;
}

function AnalysisHistory({ snapshots, latestId, selectedId, caseId, pageNumber, total, onPage, navigate }: { snapshots: AnalysisSnapshot[]; latestId: string | null; selectedId: string | null; caseId: string; pageNumber: number; total: number; onPage: (page: number) => void; navigate: (path: string) => void }) {
  if (!snapshots.length) return <EmptyState title="No analysis history" message="This case has no persisted batch-analysis snapshots yet."/>;
  return <section className="table-panel analysis-history"><div className="filter-row"><div><strong>{total} persisted snapshots</strong><p>Select a snapshot to pin all analysis result tabs to its immutable analysis ID.</p></div></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Analysis ID</th><th>Status</th><th>Created at</th><th>Version</th><th>Results</th></tr></thead><tbody>{snapshots.map(snapshot => { const latest = snapshot.analysis_id === latestId; const selected = snapshot.analysis_id === (selectedId ?? latestId); return <tr key={snapshot.analysis_id} className={selected ? "selected" : ""}><td><code>{snapshot.analysis_id}</code>{latest && <span className="snapshot-chip latest">Latest</span>}{selectedId === snapshot.analysis_id && !latest && <span className="snapshot-chip historical">Selected</span>}</td><td>{snapshot.status}</td><td>{snapshot.created_at}<small>UTC</small></td><td>Persisted snapshot</td><td><Button variant={selected ? "secondary" : "primary"} onClick={() => navigate(`/cases/${caseId}/findings${serializeQuery({ analysis: snapshot.analysis_id })}`)}>{selected ? "Viewing" : "View results"}</Button></td></tr>; })}</tbody></table></div>{total > 25 && <div className="table-footer"><Button disabled={pageNumber === 1} onClick={() => onPage(pageNumber - 1)}>Previous</Button><span>Page {pageNumber} · showing up to 25 of {total}</span><Button disabled={pageNumber * 25 >= total} onClick={() => onPage(pageNumber + 1)}>Next</Button></div>}</section>;
}

function SectionEmpty({ section, filtered, analyzed, snapshotLabel, caseId, onClear, navigate, onRun, runDisabled }: { section: string; filtered: boolean; analyzed: boolean; snapshotLabel: string; caseId: string; onClear: () => void; navigate: (path: string) => void; onRun: () => void; runDisabled: boolean }) {
  if (filtered) return <EmptyState title={`No ${section} match this filter`} message="The persisted result set is unchanged; clear the active filter to see it." action="Clear filter" onAction={onClear}/>;
  if (section === "evidence") return <EmptyState title="No evidence imported" message="This case has no persisted evidence. Import a supported CSV or JSON file to begin." action="Import evidence" onAction={() => navigate(`/import?case=${caseId}`)}/>;
  if (analysisSections.has(section) && !analyzed) return <NoAnalysis onRun={onRun} disabled={runDisabled}/>;
  if (section === "findings" && analyzed) return <EmptyState title="Analysis completed with no findings" message={`The persisted ${snapshotLabel} completed successfully and produced zero findings.`}/>;
  return <EmptyState title={analyzed && analysisSections.has(section) ? `Analysis completed with no ${section}` : `No ${section}`} message={analyzed && analysisSections.has(section) ? `The persisted ${snapshotLabel} produced no ${section}.` : "The backend returned no persisted records for this case."}/>;
}

function NoAnalysis({ onRun, disabled }: { onRun: () => void; disabled: boolean }) { return <EmptyState title="No analysis has run" message="This case has no persisted analysis snapshot, so analysis result sections are not available yet." action={disabled ? "Running analysis…" : "Run analysis"} actionDisabled={disabled} onAction={onRun}/>; }
function EmptyState({ title, message, action, onAction, actionDisabled = false }: { title: string; message: string; action?: string; onAction?: () => void; actionDisabled?: boolean }) { return <div className="state-box"><strong>{title}</strong><p>{message}</p>{action && onAction && <Button disabled={actionDisabled} onClick={onAction}>{action}</Button>}</div>; }

function RecordTable({ section, items, columns: requested, selectedId, onSelect }: { section: string; items: Record<string, unknown>[]; columns?: string[]; selectedId?: string; onSelect?: (item: InvestigationRecordViewModel) => void }) {
  if (!items.length) return <EmptyState title={`No ${section}`} message="The backend returned no persisted records for this section."/>;
  const kind = section.split(" ")[0] as InvestigationRecordKind; const mapped = mapInvestigationRecords(kind, items);
  const visible = requested?.filter(column => items.some(item => column in item || (column === "risk_score" && ("risk" in item || "score" in item)))) ?? Object.keys(items[0]).filter(key => typeof items[0][key] !== "object").slice(0, 6);
  return <div className="data-table-wrap"><table className="data-table"><thead><tr>{visible.map(column => <th key={column}>{heading(column)}</th>)}{onSelect && <th>Details</th>}</tr></thead><tbody>{mapped.map(item => <tr key={item.id} className={selectedId === item.id ? "selected" : ""}>{visible.map(column => <td key={column}>{display(valueFor(item.source as Record<string, unknown>, column))}</td>)}{onSelect && <td><button className="record-inspect" onClick={() => onSelect(item)} aria-label={`Inspect ${item.id}`}>Inspect</button></td>}</tr>)}</tbody></table></div>;
}

function RecordDetail({ item, caseId, analysisId, navigate, onClose }: { item: InvestigationRecordViewModel; caseId: string; analysisId?: string | null; navigate: (path: string) => void; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const close = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [item.id, onClose]);
  return <div className="record-detail-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}><aside className="record-detail-panel" role="dialog" aria-modal="true" aria-label={`Details for ${item.id}`}><header><div><span>{heading(item.kind)} record</span><h2>{item.title}</h2><code>{item.id}</code></div><button ref={closeRef} className="record-detail-close" onClick={onClose} aria-label="Close record details">×</button></header><dl className="record-details">{Object.entries(item.source).map(([key, value]) => <DetailValue key={key} name={key} value={value} caseId={caseId} analysisId={analysisId} navigate={navigate}/>)}</dl></aside></div>;
}

function DetailValue({ name, value, caseId, analysisId, navigate }: { name: string; value: unknown; caseId: string; analysisId?: string | null; navigate: (path: string) => void }) {
  if ((name === "evidence_ids" || name === "event_ids" || name === "trigger_event_ids") && Array.isArray(value)) {
    const target = name === "evidence_ids" ? "evidence" : "event";
    const visible = value.slice(0, 100);
    return <div><dt>{heading(name)}</dt><dd className="reference-links">{visible.map(id => <button key={String(id)} onClick={() => navigate(`/cases/${caseId}/${target === "evidence" ? "evidence" : "events"}${serializeQuery({ [target]: String(id), analysis: analysisId })}`)}>{String(id)}</button>)}{value.length > visible.length && <small>Showing the first {visible.length.toLocaleString()} of {value.length.toLocaleString()} persisted references.</small>}</dd></div>;
  }
  if (Array.isArray(value)) { const visible = value.slice(0, 100); return <div><dt>{heading(name)}</dt><dd>{value.length ? <details className="detail-array"><summary>{value.length.toLocaleString()} persisted item{value.length === 1 ? "" : "s"}</summary><ol className="structured-list">{visible.map((entry, index) => <li key={index}>{typeof entry === "object" && entry !== null ? <NestedFields value={record(entry)}/> : display(entry)}</li>)}</ol>{value.length > visible.length && <small>Showing the first {visible.length.toLocaleString()} items to keep this panel responsive.</small>}</details> : "—"}</dd></div>; }
  if (value && typeof value === "object") return <div><dt>{heading(name)}</dt><dd><NestedFields value={record(value)}/></dd></div>;
  return <div><dt>{heading(name)}</dt><dd>{display(value)}</dd></div>;
}

function NestedFields({ value }: { value: Record<string, unknown> }) { return <dl className="nested-fields">{Object.entries(value).map(([key, nested]) => <div key={key}><dt>{heading(key)}</dt><dd><NestedValue value={nested}/></dd></div>)}</dl>; }
function NestedValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) return value.length ? <ol className="structured-list">{value.map((entry, index) => <li key={index}><NestedValue value={entry}/></li>)}</ol> : <>—</>;
  if (value && typeof value === "object") return <NestedFields value={record(value)}/>;
  return <>{display(value)}</>;
}
