import { useEffect, useState } from "react";
import { apiClient } from "../api/batch";
import { normalizeApiError } from "../api/client";
import { Button, PageHeader } from "../components/ui/core";

interface PageResult { items: Record<string, unknown>[]; total: number }

export function ConnectedCaseWorkspacePage({ path, navigate }: { path: string; navigate: (path: string) => void }) {
  const [, , id = "", requested = "overview"] = path.split("/");
  const section = requested === "analytics" ? "aggregates" : requested;
  const [data, setData] = useState<unknown>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const endpoint = section === "overview" ? `/cases/${id}/summary` : section === "graph" || section === "aggregates" ? `/cases/${id}/${section}` : `/cases/${id}/${section}?page=1&page_size=50`;
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError(null);
    void apiClient.request<unknown>(endpoint, { signal: controller.signal }).then(setData).catch(reason => { if (!controller.signal.aborted) setError(normalizeApiError(reason).message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [endpoint]);
  const reanalyze = async () => { setLoading(true); try { await apiClient.request(`/cases/${id}/analyses`, { method: "POST" }); navigate(`/cases/${id}/findings`); } catch (reason) { setError(normalizeApiError(reason).message); setLoading(false); } };
  const page = data as PageResult | null; const items = page && Array.isArray(page.items) ? page.items : [];
  return <><PageHeader eyebrow={`Persisted batch case · CASE-${id.padStart(4, "0")}`} title={section === "overview" ? "Case overview" : section[0].toUpperCase() + section.slice(1)} description="Connected batch results retain backend IDs, UTC timestamps, provenance, and rule traces." actions={<><Button onClick={() => navigate("/import")}>Import evidence</Button><Button variant="primary" onClick={reanalyze}>Reanalyze</Button></>}/>
    <nav className="case-tabs" aria-label="Connected case views">{["overview","evidence","events","findings","alerts","incidents","timeline","graph","analytics"].map(tab => <button className={(requested === tab || (requested === "overview" && tab === "overview")) ? "active" : ""} onClick={() => navigate(`/cases/${id}/${tab}`)} key={tab}>{tab}</button>)}</nav>
    {loading && <div className="state-box" aria-live="polite"><strong>Loading persisted {section}…</strong></div>}
    {error && <div className="state-box" role="alert"><strong>Connected view unavailable</strong><p>{error}</p><Button onClick={() => navigate(path)}>Retry</Button></div>}
    {!loading && !error && section === "overview" && <pre className="table-panel connected-json">{JSON.stringify(data, null, 2)}</pre>}
    {!loading && !error && section === "graph" && <pre className="table-panel connected-json">{JSON.stringify(data, null, 2)}</pre>}
    {!loading && !error && section === "aggregates" && <pre className="table-panel connected-json">{JSON.stringify(data, null, 2)}</pre>}
    {!loading && !error && !["overview","graph","aggregates"].includes(section) && <div className="table-panel"><div className="table-footer"><span>{page?.total ?? 0} persisted records</span></div>{items.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Record</th></tr></thead><tbody>{items.map((item, index) => <tr key={String(item.event_id ?? item.evidence_id ?? item.finding_id ?? item.alert_id ?? item.incident_id ?? index)}><td><pre>{JSON.stringify(item, null, 2)}</pre></td></tr>)}</tbody></table></div> : <div className="state-box"><span>◇</span><strong>No {section}</strong><p>The backend returned an empty result for this case and filter.</p></div>}</div>}
  </>;
}
