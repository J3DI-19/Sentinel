import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/batch";
import { phase3Api } from "../api/phase3";
import { normalizeApiError, serializeQuery } from "../api/client";
import { Button, MetricCard, PageHeader } from "../components/ui/core";
import { ConnectedReportsPanel } from "./ConnectedReportsPanel";
import { mapInvestigationRecords, type InvestigationRecordKind } from "../features/investigation/viewModels";

interface PageResult { items?: Record<string, unknown>[]; total?: number }
const names: Record<string, string> = { overview: "Case overview", evidence: "Evidence", events: "Canonical events", findings: "Findings", alerts: "Alerts", incidents: "Incidents", timeline: "Timeline", graph: "Entity graph", aggregates: "Analytics", reports: "Reports", audit: "Audit history" };
const columns: Record<string, string[]> = { evidence: ["evidence_id", "original_name", "source", "sha256", "created_at"], events: ["event_id", "timestamp", "origin", "event_type", "entity_id"], findings: ["finding_id", "title", "severity", "score", "rule_id"], alerts: ["alert_id", "title", "severity", "status", "created_at"], incidents: ["incident_id", "title", "severity", "status", "started_at"], timeline: ["timeline_id", "timestamp", "kind", "title", "severity"], audit: ["occurred_at", "action", "actor", "subject_type", "subject_id", "request_id"] };
const text = (value: unknown) => value == null ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
const heading = (value: string) => value.replaceAll("_", " ");

export function ConnectedCaseWorkspaceV3Page({ path, navigate }: { path: string; navigate: (path: string) => void }) {
  const [, , id = "", requested = "overview"] = path.split("/"); const caseId = Number(id); const section = requested === "analytics" ? "aggregates" : requested;
  const [data, setData] = useState<unknown>(null); const [loading, setLoading] = useState(section !== "reports"); const [error, setError] = useState<string | null>(null); const [query, setQuery] = useState(""); const [pageNumber, setPageNumber] = useState(1);
  const endpoint = useMemo(() => {
    if (section === "overview") return `/cases/${id}/summary`;
    if (["graph", "aggregates"].includes(section)) return `/cases/${id}/${section}`;
    const filter = section === "events" ? { event_type: query || undefined } : section === "evidence" ? { source: query || undefined } : ["findings", "alerts", "incidents", "timeline"].includes(section) ? { severity: query || undefined } : {};
    return `/cases/${id}/${section}${serializeQuery({ page: pageNumber, page_size: 50, ...filter })}`;
  }, [id, pageNumber, query, section]);
  useEffect(() => { setPageNumber(1); }, [section]);
  useEffect(() => { if (section === "reports") { setLoading(false); setError(null); return; } const controller = new AbortController(); setLoading(true); setError(null); const request = section === "audit" ? phase3Api.audit(caseId, controller.signal) : apiClient.request<unknown>(endpoint, { signal: controller.signal }); void request.then(setData).catch(reason => { if (!controller.signal.aborted) setError(normalizeApiError(reason).message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); }); return () => controller.abort(); }, [caseId, endpoint, section]);
  const reanalyze = async () => { setLoading(true); try { await apiClient.request(`/cases/${id}/analyses`, { method: "POST" }); navigate(`/cases/${id}/findings`); } catch (reason) { setError(normalizeApiError(reason).message); setLoading(false); } };
  const object = (data ?? {}) as Record<string, unknown>; const result = object as PageResult; const all = Array.isArray(result.items) ? result.items : []; const items = all; const graph = object as { nodes?: Record<string, unknown>[]; edges?: Record<string, unknown>[]; truncated?: boolean };
  return <><PageHeader eyebrow={`Persisted investigation · CASE-${id.padStart(4, "0")}`} title={names[section] ?? heading(section)} description="Connected records preserve backend IDs, UTC timestamps, nulls, provenance, rule traces, and authoritative risk factors." actions={<><Button onClick={() => navigate("/import")}>Import evidence</Button><Button onClick={() => navigate(`/live?case=${id}`)}>Live capture</Button><Button variant="primary" onClick={reanalyze}>Reanalyze</Button></>}/>
    <nav className="case-tabs" aria-label="Connected case views">{["overview","evidence","events","findings","alerts","incidents","timeline","graph","analytics","reports","audit"].map(tab => <button className={requested === tab ? "active" : ""} onClick={() => navigate(`/cases/${id}/${tab}`)} key={tab}>{tab}</button>)}</nav>
    {loading && <div className="state-box" aria-live="polite"><strong>Loading persisted {heading(section)}…</strong></div>}
    {error && <div className="state-box" role="alert"><strong>Connected view unavailable</strong><p>{error}</p><Button onClick={() => navigate(path)}>Retry</Button></div>}
    {!loading && !error && section === "reports" && <ConnectedReportsPanel caseId={caseId}/>}
    {!loading && !error && section === "overview" && <div className="metrics-grid">{Object.entries(object).filter(([, value]) => value == null || ["string", "number", "boolean"].includes(typeof value)).map(([key, value]) => <MetricCard key={key} label={heading(key)} value={text(value)} detail={key.includes("time") || key.endsWith("_at") ? "UTC" : "Backend value"}/>)}</div>}
    {!loading && !error && section === "graph" && <section className="table-panel">{graph.truncated && <div className="settings-notice" role="status"><div><b>Partial graph</b><p>The backend applied node or edge safety limits. Refine the case scope before drawing conclusions.</p></div></div>}<div className="metrics-grid"><MetricCard label="Nodes" value={graph.nodes?.length ?? 0}/><MetricCard label="Edges" value={graph.edges?.length ?? 0}/><MetricCard label="Truncated" value={graph.truncated ? "Yes" : "No"}/></div><RecordTable section="graph nodes" items={graph.nodes ?? []}/><RecordTable section="graph edges" items={graph.edges ?? []}/></section>}
    {!loading && !error && section === "aggregates" && <RecordTable section="aggregates" items={all.length ? all : Object.entries(object).map(([metric, value]) => ({ metric, value }))}/>}
    {!loading && !error && !["overview", "graph", "aggregates", "reports"].includes(section) && <section className="table-panel"><div className="filter-row"><input className="input" aria-label={`Filter ${section}`} placeholder={section === "events" ? "Exact event type" : section === "evidence" ? "Exact source" : ["findings", "alerts", "incidents", "timeline"].includes(section) ? "Exact severity" : `Filter ${section}`} value={query} onChange={event => { setQuery(event.target.value); setPageNumber(1); }}/><span>{result.total ?? 0} persisted records</span></div><RecordTable section={section} items={items} columns={columns[section]} filtered={Boolean(query)}/>{(result.total ?? 0) > 50 && <div className="table-footer"><Button disabled={pageNumber === 1} onClick={() => setPageNumber(value => value - 1)}>Previous</Button><span>Page {pageNumber}</span><Button disabled={pageNumber * 50 >= (result.total ?? 0)} onClick={() => setPageNumber(value => value + 1)}>Next</Button></div>}</section>}
  </>;
}

function RecordTable({ section, items, columns: requested, filtered = false }: { section: string; items: Record<string, unknown>[]; columns?: string[]; filtered?: boolean }) {
  if (!items.length) return <div className="state-box"><strong>{filtered ? `No ${section} match this filter` : `No ${section}`}</strong><p>{filtered ? "The backend returned no records for the active filter." : "The backend returned no records for this case."}</p></div>;
  const kind = section.split(" ")[0] as InvestigationRecordKind;
  const mapped = mapInvestigationRecords(kind, items);
  const visible = requested?.filter(column => items.some(item => column in item)) ?? Object.keys(items[0]).filter(key => typeof items[0][key] !== "object").slice(0, 6);
  return <div className="data-table-wrap"><table className="data-table"><thead><tr>{visible.map(column => <th key={column}>{heading(column)}</th>)}<th>Details</th></tr></thead><tbody>{mapped.map(item => <tr key={item.id}>{visible.map(column => <td key={column}>{text(item.source[column])}</td>)}<td><details><summary>Inspect</summary><dl className="record-details">{Object.entries(item.source).map(([key, value]) => <div key={key}><dt>{heading(key)}</dt><dd>{text(value)}</dd></div>)}</dl></details></td></tr>)}</tbody></table></div>;
}
