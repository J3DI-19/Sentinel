import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/batch";
import { phase3Api } from "../api/phase3";
import { normalizeApiError, serializeQuery } from "../api/client";
import { Button, MetricCard, PageHeader } from "../components/ui/core";
import { ConnectedReportsPanel } from "./ConnectedReportsPanel";
import { mapInvestigationRecords, type InvestigationRecordKind, type InvestigationRecordViewModel } from "../features/investigation/viewModels";

interface PageResult { items?: Record<string, unknown>[]; page?: number; page_size?: number; total?: number }
interface CaseSummary { analysis_id?: string | null; event_count?: number; [key: string]: unknown }
interface AnalysisSnapshot { analysis_id: string; case_id: number; status: string; created_at: string }
const names: Record<string, string> = { overview: "Case overview", evidence: "Evidence", events: "Canonical events", history: "Analysis history", findings: "Findings", alerts: "Alerts", incidents: "Incidents", timeline: "Timeline", graph: "Entity graph", charts: "Charts", aggregates: "Analytics", reports: "Reports", audit: "Audit history" };
const columns: Record<string, string[]> = {
  evidence: ["evidence_id", "original_name", "source_type", "status", "sha256", "received_at"],
  events: ["event_id", "observed_at", "origin", "event_type", "entity_id"],
  findings: ["finding_id", "title", "severity", "risk_score", "rule_id"],
  alerts: ["alert_id", "title", "severity", "risk_score", "triggered_at"],
  incidents: ["incident_id", "maximum_risk", "started_at", "ended_at"],
  timeline: ["entry_id", "occurred_at", "entry_type", "title", "severity", "risk_score"],
  audit: ["occurred_at", "action", "actor", "subject_type", "subject_id", "request_id"],
  aggregates: ["series", "category", "subgroup", "value"],
  charts: ["series", "category", "subgroup", "value"],
  "graph nodes": ["node_id", "kind", "label", "event_count", "maximum_risk"],
  "graph edges": ["edge_id", "source_node_id", "target_node_id", "relationships", "event_count"],
};
const analysisSections = new Set(["findings", "alerts", "incidents", "timeline", "graph", "charts", "aggregates"]);
const heading = (value: string) => value.replaceAll("_", " ");
const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const display = (value: unknown): string => value == null ? "—" : typeof value === "boolean" ? (value ? "Yes" : "No") : Array.isArray(value) ? value.join(", ") : typeof value === "object" ? "Structured details" : String(value);
const valueFor = (item: Record<string, unknown>, column: string): unknown => column === "risk_score" ? item.risk_score ?? item.score ?? record(item.risk).score : item[column];
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function ConnectedCaseWorkspaceV3Page({ path, search = "", navigate }: { path: string; search?: string; navigate: (path: string) => void }) {
  const [, , id = "", requested = "overview"] = path.split("/"); const caseId = Number(id); const section = requested === "analytics" ? "aggregates" : requested;
  const requestedAnalysis = new URLSearchParams(search).get("analysis");
  const selectedAnalysisId = requestedAnalysis && uuid.test(requestedAnalysis) ? requestedAnalysis : null;
  const snapshotSearch = selectedAnalysisId ? serializeQuery({ analysis: selectedAnalysisId }) : "";
  const [data, setData] = useState<unknown>(null); const [summary, setSummary] = useState<CaseSummary | null>(null);
  const [loading, setLoading] = useState(section !== "reports"); const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState(""); const [pageNumber, setPageNumber] = useState(1); const [reload, setReload] = useState(0);
  const [selected, setSelected] = useState<InvestigationRecordViewModel | null>(null);
  const [referenceError, setReferenceError] = useState<string | null>(null); const [resolvingReference, setResolvingReference] = useState(false);
  const endpoint = useMemo(() => {
    if (section === "overview") return `/cases/${id}/summary`;
    if (section === "history") return `/cases/${id}/analyses${serializeQuery({ page: pageNumber, page_size: 25 })}`;
    if (["graph", "charts", "aggregates"].includes(section)) return `/cases/${id}/${section}${serializeQuery({ analysis_id: selectedAnalysisId })}`;
    const filter = section === "events" ? { event_type: query || undefined } : section === "evidence" ? { source: query || undefined } : ["findings", "alerts", "incidents", "timeline"].includes(section) ? { severity: query || undefined } : {};
    return `/cases/${id}/${section}${serializeQuery({ page: pageNumber, page_size: 50, ...filter, analysis_id: analysisSections.has(section) ? selectedAnalysisId : null })}`;
  }, [id, pageNumber, query, section, selectedAnalysisId]);

  useEffect(() => { setPageNumber(1); setQuery(""); setSelected(null); setReferenceError(null); }, [section]);
  useEffect(() => { setPageNumber(1); setSelected(null); }, [selectedAnalysisId]);
  useEffect(() => {
    if (requestedAnalysis && !selectedAnalysisId) { setLoading(false); setError("The selected analysis ID is malformed. Open Analysis history and choose a persisted snapshot."); return; }
    const controller = new AbortController(); setLoading(true); setError(null);
    const summaryRequest = apiClient.request<CaseSummary>(`/cases/${id}/summary`, { signal: controller.signal });
    const dataRequest: Promise<unknown> = section === "reports" ? Promise.resolve(null) : section === "audit" ? phase3Api.audit(caseId, controller.signal) : section === "overview" ? summaryRequest : apiClient.request<unknown>(endpoint, { signal: controller.signal });
    const snapshotRequest = selectedAnalysisId ? apiClient.request(`/cases/${id}/analyses/${selectedAnalysisId}`, { signal: controller.signal }) : Promise.resolve(null);
    void Promise.all([summaryRequest, dataRequest, snapshotRequest]).then(([nextSummary, nextData]) => { setSummary(nextSummary); setData(section === "overview" ? nextSummary : nextData); }).catch(reason => { if (!controller.signal.aborted) setError(normalizeApiError(reason).message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [caseId, endpoint, id, reload, requestedAnalysis, section, selectedAnalysisId]);

  const object = record(data); const result = object as PageResult; const all = Array.isArray(result.items) ? result.items : [];
  const graph = object as { nodes?: Record<string, unknown>[]; edges?: Record<string, unknown>[]; truncated?: boolean };
  const mapped = mapInvestigationRecords(section as InvestigationRecordKind, all);
  useEffect(() => {
    if (loading || error || !["evidence", "events"].includes(section)) return;
    const parameter = section === "evidence" ? "evidence" : "event"; const requestedId = new URLSearchParams(search).get(parameter);
    if (!requestedId) { setReferenceError(null); setSelected(mapped[0] ?? null); return; }
    if (!uuid.test(requestedId)) { setSelected(null); setReferenceError(`The requested ${parameter} reference is malformed.`); return; }
    const existing = mapped.find(item => item.id === requestedId);
    if (existing) { setSelected(existing); setReferenceError(null); return; }
    const controller = new AbortController(); setResolvingReference(true); setReferenceError(null);
    const detailPath = section === "evidence" ? `/cases/${id}/evidence/${requestedId}` : `/cases/${id}/events/${requestedId}`;
    void apiClient.request<Record<string, unknown>>(detailPath, { signal: controller.signal }).then(value => setSelected(mapInvestigationRecords(section as InvestigationRecordKind, [value])[0])).catch(() => { if (!controller.signal.aborted) { setSelected(null); setReferenceError(`The requested ${parameter} is unavailable or does not belong to this case.`); } }).finally(() => { if (!controller.signal.aborted) setResolvingReference(false); });
    return () => controller.abort();
  }, [data, error, id, loading, search, section]);

  const reanalyze = async () => { setLoading(true); setError(null); try { await apiClient.request(`/cases/${id}/analyses`, { method: "POST" }); navigate(`/cases/${id}/findings`); } catch (reason) { setError(normalizeApiError(reason).message); setLoading(false); } };
  const selectRecord = (item: InvestigationRecordViewModel) => { const analysis = selectedAnalysisId ?? undefined; setSelected(item); if (section === "evidence") navigate(`/cases/${id}/evidence${serializeQuery({ evidence: item.id, analysis })}`); else if (section === "events") navigate(`/cases/${id}/events${serializeQuery({ event: item.id, analysis })}`); };
  const total = result.total ?? all.length; const start = total ? (pageNumber - 1) * 50 + 1 : 0; const end = Math.min(pageNumber * 50, total);
  const viewingHistorical = Boolean(selectedAnalysisId && summary?.analysis_id !== selectedAnalysisId);
  const snapshotLabel = viewingHistorical ? "historical analysis" : "latest analysis";

  return <><PageHeader eyebrow={`Persisted investigation · CASE-${id.padStart(4, "0")}`} title={names[section] ?? heading(section)} description="Connected records preserve backend IDs, UTC timestamps, nulls, provenance, rule traces, and authoritative risk factors." actions={<><Button onClick={() => navigate(`/cases/${id}/history${snapshotSearch}`)}>Analysis history</Button><Button onClick={() => navigate(`/import?case=${id}`)}>Import evidence</Button><Button onClick={() => navigate(`/live?case=${id}`)}>Live capture</Button><Button variant="primary" onClick={reanalyze}>Reanalyze</Button></>}/>
    <nav className="case-tabs" aria-label="Connected case views">{["overview","evidence","events","history","findings","alerts","incidents","timeline","graph","charts","analytics","reports","audit"].map(tab => <button className={requested === tab ? "active" : ""} onClick={() => navigate(`/cases/${id}/${tab}${snapshotSearch}`)} key={tab}>{tab === "history" ? "analysis history" : tab}</button>)}</nav>
    {loading && <div className="state-box" aria-live="polite"><strong>Loading persisted {heading(section)}…</strong><p>Traceveil is reading case-owned records from the backend.</p></div>}
    {error && <div className="state-box" role="alert"><strong>{requestedAnalysis ? "Selected analysis unavailable" : "Connected view unavailable"}</strong><p>{error}</p>{requestedAnalysis ? <Button onClick={() => navigate(`/cases/${id}/history`)}>Open analysis history</Button> : <Button onClick={() => setReload(value => value + 1)}>Retry</Button>}</div>}
    {!loading && !error && summary?.analysis_id && (analysisSections.has(section) || section === "history") && <div className={`analysis-snapshot-banner ${viewingHistorical ? "historical" : "latest"}`} role="status"><div><span>{viewingHistorical ? "Historical snapshot" : "Latest snapshot"}</span><b>{selectedAnalysisId ?? summary.analysis_id}</b><p>{viewingHistorical ? "Results are pinned to a persisted historical analysis and will stay selected across case tabs." : "Results use the case's latest persisted analysis."}</p></div>{viewingHistorical && <Button onClick={() => navigate(`/cases/${id}/${section}`)}>View latest</Button>}</div>}
    {!loading && !error && referenceError && <div className="settings-notice reference-warning" role="alert"><div><b>Source reference unavailable</b><p>{referenceError} The surrounding persisted results remain available.</p></div><Button onClick={() => navigate(`/cases/${id}/${section}${snapshotSearch}`)}>Clear reference</Button></div>}
    {!loading && !error && resolvingReference && <div className="settings-notice" role="status"><div><b>Opening source record</b><p>Resolving the case-owned reference from persisted data…</p></div></div>}
    {!loading && !error && section === "reports" && <ConnectedReportsPanel caseId={caseId}/>}
    {!loading && !error && section === "history" && <AnalysisHistory snapshots={all as unknown as AnalysisSnapshot[]} latestId={summary?.analysis_id ?? null} selectedId={selectedAnalysisId} caseId={id} pageNumber={pageNumber} total={total} onPage={setPageNumber} navigate={navigate}/>}
    {!loading && !error && section === "overview" && <><div className="metrics-grid">{Object.entries(object).filter(([, value]) => value == null || ["string", "number", "boolean"].includes(typeof value)).map(([key, value]) => <MetricCard key={key} label={heading(key)} value={display(value)} detail={key.includes("time") || key.endsWith("_at") ? "UTC" : "Persisted backend value"}/>)}</div>{!summary?.analysis_id && <EmptyState title="No analysis has run" message="This case has no persisted analysis snapshot yet. Import evidence or run deterministic analysis to create result sections." action="Import evidence" onAction={() => navigate(`/import?case=${id}`)}/>}</>}
    {!loading && !error && section === "graph" && (summary?.analysis_id ? <section className="table-panel">{graph.truncated && <div className="settings-notice" role="status"><div><b>Partial graph</b><p>The backend applied node or edge safety limits. This view is not the complete graph.</p></div></div>}<div className="metrics-grid"><MetricCard label="Nodes" value={graph.nodes?.length ?? 0}/><MetricCard label="Edges" value={graph.edges?.length ?? 0}/><MetricCard label="Truncated" value={graph.truncated ? "Yes" : "No"}/></div><RecordTable section="graph nodes" items={graph.nodes ?? []}/><RecordTable section="graph edges" items={graph.edges ?? []}/></section> : <NoAnalysis onRun={reanalyze}/>)}
    {!loading && !error && (section === "aggregates" || section === "charts") && (summary?.analysis_id ? (all.length ? <RecordTable section={section} items={all} columns={columns[section]}/> : <EmptyState title={`Analysis completed with no ${section}`} message={`The persisted ${snapshotLabel} completed, but there are no ${section} points for its selected events.`}/>) : <NoAnalysis onRun={reanalyze}/>)}
    {!loading && !error && !["overview", "history", "graph", "charts", "aggregates", "reports"].includes(section) && <section className="workspace-results"><div className="table-panel"><div className="filter-row"><input className="input" aria-label={`Filter ${section}`} placeholder={section === "events" ? "Exact event type" : section === "evidence" ? "Exact source" : ["findings", "alerts", "incidents", "timeline"].includes(section) ? "Exact severity" : `Filter ${section}`} value={query} onChange={event => { setQuery(event.target.value); setPageNumber(1); }}/><span>{total ? `Showing ${start}–${end} of ${total} persisted records` : "0 persisted records"}</span></div>{all.length ? <RecordTable section={section} items={all} columns={columns[section]} selectedId={selected?.id} onSelect={selectRecord}/> : <SectionEmpty section={section} filtered={Boolean(query)} analyzed={Boolean(summary?.analysis_id)} snapshotLabel={snapshotLabel} caseId={id} onClear={() => setQuery("")} navigate={navigate} onRun={reanalyze}/>} {total > 50 && <div className="table-footer"><Button disabled={pageNumber === 1} onClick={() => setPageNumber(value => value - 1)}>Previous</Button><span>Page {pageNumber} · partial view of {total}</span><Button disabled={pageNumber * 50 >= total} onClick={() => setPageNumber(value => value + 1)}>Next</Button></div>}</div>{selected && <RecordDetail item={selected} caseId={id} analysisId={selectedAnalysisId} navigate={navigate}/>}</section>}
  </>;
}

function AnalysisHistory({ snapshots, latestId, selectedId, caseId, pageNumber, total, onPage, navigate }: { snapshots: AnalysisSnapshot[]; latestId: string | null; selectedId: string | null; caseId: string; pageNumber: number; total: number; onPage: (page: number) => void; navigate: (path: string) => void }) {
  if (!snapshots.length) return <EmptyState title="No analysis history" message="This case has no persisted batch-analysis snapshots yet."/>;
  return <section className="table-panel analysis-history"><div className="filter-row"><div><strong>{total} persisted snapshots</strong><p>Select a snapshot to pin all analysis result tabs to its immutable analysis ID.</p></div></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Analysis ID</th><th>Status</th><th>Created at</th><th>Version</th><th>Results</th></tr></thead><tbody>{snapshots.map(snapshot => { const latest = snapshot.analysis_id === latestId; const selected = snapshot.analysis_id === (selectedId ?? latestId); return <tr key={snapshot.analysis_id} className={selected ? "selected" : ""}><td><code>{snapshot.analysis_id}</code>{latest && <span className="snapshot-chip latest">Latest</span>}{selectedId === snapshot.analysis_id && !latest && <span className="snapshot-chip historical">Selected</span>}</td><td>{snapshot.status}</td><td>{snapshot.created_at}<small>UTC</small></td><td>Persisted snapshot</td><td><Button variant={selected ? "secondary" : "primary"} onClick={() => navigate(`/cases/${caseId}/findings${serializeQuery({ analysis: snapshot.analysis_id })}`)}>{selected ? "Viewing" : "View results"}</Button></td></tr>; })}</tbody></table></div>{total > 25 && <div className="table-footer"><Button disabled={pageNumber === 1} onClick={() => onPage(pageNumber - 1)}>Previous</Button><span>Page {pageNumber} · showing up to 25 of {total}</span><Button disabled={pageNumber * 25 >= total} onClick={() => onPage(pageNumber + 1)}>Next</Button></div>}</section>;
}

function SectionEmpty({ section, filtered, analyzed, snapshotLabel, caseId, onClear, navigate, onRun }: { section: string; filtered: boolean; analyzed: boolean; snapshotLabel: string; caseId: string; onClear: () => void; navigate: (path: string) => void; onRun: () => void }) {
  if (filtered) return <EmptyState title={`No ${section} match this filter`} message="The persisted result set is unchanged; clear the active filter to see it." action="Clear filter" onAction={onClear}/>;
  if (section === "evidence") return <EmptyState title="No evidence imported" message="This case has no persisted evidence. Import a supported CSV or JSON file to begin." action="Import evidence" onAction={() => navigate(`/import?case=${caseId}`)}/>;
  if (analysisSections.has(section) && !analyzed) return <NoAnalysis onRun={onRun}/>;
  if (section === "findings" && analyzed) return <EmptyState title="Analysis completed with no findings" message={`The persisted ${snapshotLabel} completed successfully and produced zero findings.`}/>;
  return <EmptyState title={analyzed && analysisSections.has(section) ? `Analysis completed with no ${section}` : `No ${section}`} message={analyzed && analysisSections.has(section) ? `The persisted ${snapshotLabel} produced no ${section}.` : "The backend returned no persisted records for this case."}/>;
}

function NoAnalysis({ onRun }: { onRun: () => void }) { return <EmptyState title="No analysis has run" message="This case has no persisted analysis snapshot, so analysis result sections are not available yet." action="Run analysis" onAction={onRun}/>; }
function EmptyState({ title, message, action, onAction }: { title: string; message: string; action?: string; onAction?: () => void }) { return <div className="state-box"><strong>{title}</strong><p>{message}</p>{action && onAction && <Button onClick={onAction}>{action}</Button>}</div>; }

function RecordTable({ section, items, columns: requested, selectedId, onSelect }: { section: string; items: Record<string, unknown>[]; columns?: string[]; selectedId?: string; onSelect?: (item: InvestigationRecordViewModel) => void }) {
  if (!items.length) return <EmptyState title={`No ${section}`} message="The backend returned no persisted records for this section."/>;
  const kind = section.split(" ")[0] as InvestigationRecordKind; const mapped = mapInvestigationRecords(kind, items);
  const visible = requested?.filter(column => items.some(item => column in item || (column === "risk_score" && ("risk" in item || "score" in item)))) ?? Object.keys(items[0]).filter(key => typeof items[0][key] !== "object").slice(0, 6);
  return <div className="data-table-wrap"><table className="data-table"><thead><tr>{visible.map(column => <th key={column}>{heading(column)}</th>)}{onSelect && <th>Details</th>}</tr></thead><tbody>{mapped.map(item => <tr key={item.id} className={selectedId === item.id ? "selected" : ""}>{visible.map(column => <td key={column}>{display(valueFor(item.source as Record<string, unknown>, column))}</td>)}{onSelect && <td><button className="record-inspect" onClick={() => onSelect(item)} aria-label={`Inspect ${item.id}`}>Inspect</button></td>}</tr>)}</tbody></table></div>;
}

function RecordDetail({ item, caseId, analysisId, navigate }: { item: InvestigationRecordViewModel; caseId: string; analysisId?: string | null; navigate: (path: string) => void }) {
  return <aside className="record-detail-panel" aria-label={`Details for ${item.id}`}><header><div><span>{heading(item.kind)} record</span><h2>{item.title}</h2><code>{item.id}</code></div></header><dl className="record-details">{Object.entries(item.source).map(([key, value]) => <DetailValue key={key} name={key} value={value} caseId={caseId} analysisId={analysisId} navigate={navigate}/>)}</dl></aside>;
}

function DetailValue({ name, value, caseId, analysisId, navigate }: { name: string; value: unknown; caseId: string; analysisId?: string | null; navigate: (path: string) => void }) {
  if ((name === "evidence_ids" || name === "event_ids" || name === "trigger_event_ids") && Array.isArray(value)) {
    const target = name === "evidence_ids" ? "evidence" : "event";
    return <div><dt>{heading(name)}</dt><dd className="reference-links">{value.map(id => <button key={String(id)} onClick={() => navigate(`/cases/${caseId}/${target === "evidence" ? "evidence" : "events"}${serializeQuery({ [target]: String(id), analysis: analysisId })}`)}>{String(id)}</button>)}</dd></div>;
  }
  if (Array.isArray(value)) return <div><dt>{heading(name)}</dt><dd>{value.length ? <ol className="structured-list">{value.map((entry, index) => <li key={index}>{typeof entry === "object" && entry !== null ? <NestedFields value={record(entry)}/> : display(entry)}</li>)}</ol> : "—"}</dd></div>;
  if (value && typeof value === "object") return <div><dt>{heading(name)}</dt><dd><NestedFields value={record(value)}/></dd></div>;
  return <div><dt>{heading(name)}</dt><dd>{display(value)}</dd></div>;
}

function NestedFields({ value }: { value: Record<string, unknown> }) { return <dl className="nested-fields">{Object.entries(value).map(([key, nested]) => <div key={key}><dt>{heading(key)}</dt><dd><NestedValue value={nested}/></dd></div>)}</dl>; }
function NestedValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) return value.length ? <ol className="structured-list">{value.map((entry, index) => <li key={index}><NestedValue value={entry}/></li>)}</ol> : <>—</>;
  if (value && typeof value === "object") return <NestedFields value={record(value)}/>;
  return <>{display(value)}</>;
}
