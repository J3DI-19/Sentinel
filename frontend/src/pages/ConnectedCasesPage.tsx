import { useEffect, useMemo, useState } from "react";
import { batchApi, type ApiCase } from "../api/batch";
import { normalizeApiError } from "../api/client";
import { Button, Input, PageHeader, StatusBadge } from "../components/ui/core";

export function ConnectedCasesPage({ navigate }: { navigate:(path:string)=>void }) {
  const [items, setItems] = useState<ApiCase[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = (signal?: AbortSignal) => batchApi.listCases(signal).then(result => { setItems(Array.isArray(result.items) ? result.items : []); setError(null); }).catch(reason => { if (!signal?.aborted) setError(normalizeApiError(reason).message); }).finally(() => { if (!signal?.aborted) setLoading(false); });
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, []);
  const filtered = useMemo(() => items.filter(item => `${item.name} ${item.description} ${item.owner}`.toLowerCase().includes(search.toLowerCase())), [items, search]);
  const create = async () => {
    const name = window.prompt("Case name"); if (!name?.trim()) return;
    try { const created = await batchApi.createCase(name.trim()); setItems(current => [created, ...current]); navigate("/import"); }
    catch (reason) { setError(normalizeApiError(reason).message); }
  };
  return <><PageHeader eyebrow="Case management · Connected API" title="Cases" description="Create and open persisted batch investigations." actions={<Button variant="primary" onClick={create}>＋ New case</Button>}/>
    <div className="case-status-summary" aria-label="Case status summary"><div><b>{items.length}</b><span>Cases</span></div><div><i className="status-dot active"/><b>{items.filter(item => item.status === "active").length}</b><span>Active</span></div></div>
    <div className="table-panel cases-register"><div className="table-toolbar"><div className="search-wrap">⌕<Input placeholder="Search cases…" value={search} onChange={setSearch}/></div><span className="toolbar-spacer"/><Button onClick={() => { setLoading(true); void load(); }}>Refresh</Button></div>
      {error && <div className="state-box" role="alert"><strong>Cases could not be loaded</strong><p>{error}</p><Button onClick={() => { setLoading(true); void load(); }}>Retry</Button></div>}
      {!error && loading && <div className="state-box" aria-live="polite"><strong>Loading persisted cases…</strong></div>}
      {!error && !loading && <div className="data-table-wrap"><table className="data-table cases-table"><thead><tr><th>Case</th><th>Type</th><th>Status</th><th>Owner</th><th>Updated (UTC)</th><th/></tr></thead><tbody>{filtered.map(item => <tr key={item.id} onClick={() => navigate(`/cases/${item.id}`)} tabIndex={0} onKeyDown={event => event.key === "Enter" && navigate(`/cases/${item.id}`)}><td><div className="case-cell"><span>B</span><div><strong>{item.name}</strong><small>CASE-{String(item.id).padStart(4, "0")} · {item.description || "No description"}</small></div></div></td><td><span className="type-chip type-batch">Batch</span></td><td><StatusBadge status={item.status}/></td><td>{item.owner}</td><td>{item.updated_at ?? item.created_at}</td><td>›</td></tr>)}</tbody></table>{filtered.length === 0 && <div className="state-box"><span>◇</span><strong>{items.length ? "No matching cases" : "No persisted cases"}</strong><p>{items.length ? "Adjust the search." : "Create a case before importing evidence."}</p></div>}</div>}
      <div className="table-footer"><span>Showing {filtered.length} of {items.length} investigations</span></div></div></>;
}
