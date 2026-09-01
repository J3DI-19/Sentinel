import { useEffect, useMemo, useState, type FormEvent } from "react";
import { batchApi, type ApiCase } from "../api/batch";
import { normalizeApiError } from "../api/client";
import { Button, Input, PageHeader, StatusBadge } from "../components/ui/core";

const emptyDraft = { name: "", description: "", owner: "Investigator" };

export function ConnectedCasesPage({ navigate }: { navigate: (path: string) => void }) {
  const [items, setItems] = useState<ApiCase[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = (signal?: AbortSignal) => batchApi.listCases(signal)
    .then(result => { setItems(Array.isArray(result.items) ? result.items : []); setLoadError(null); })
    .catch(reason => { if (!signal?.aborted) setLoadError(normalizeApiError(reason).message); })
    .finally(() => { if (!signal?.aborted) setLoading(false); });
  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => controller.abort(); }, []);
  const filtered = useMemo(() => items.filter(item => `${item.name} ${item.description} ${item.owner}`.toLowerCase().includes(search.toLowerCase())), [items, search]);

  const openForm = () => { setFormOpen(true); setCreateError(null); };
  const closeForm = () => { if (!creating) { setFormOpen(false); setCreateError(null); setDraft(emptyDraft); } };
  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (creating) return;
    const name = draft.name.trim();
    const owner = draft.owner.trim();
    if (!name) { setCreateError("Enter a case name."); return; }
    if (!owner) { setCreateError("Enter a case owner."); return; }
    setCreating(true); setCreateError(null);
    try {
      const created = await batchApi.createCase(name, draft.description.trim(), owner);
      setItems(current => [created, ...current.filter(item => item.id !== created.id)]);
      setDraft(emptyDraft); setFormOpen(false);
      navigate(`/import?case=${created.id}`);
    } catch (reason) {
      setCreateError(normalizeApiError(reason).message);
    } finally {
      setCreating(false);
    }
  };

  return <><PageHeader eyebrow="Case management · Connected API" title="Cases" description="Create and open persisted batch investigations." actions={<Button variant="primary" onClick={openForm} disabled={formOpen}>＋ New case</Button>}/>
    {formOpen && <form className="table-panel case-create-panel" aria-label="Create case" onSubmit={create}>
      <div><span className="eyebrow">New persisted investigation</span><h2>Create case</h2><p>Define the case before importing evidence.</p></div>
      <div className="case-create-fields">
        <label><span>Case name</span><input autoFocus required maxLength={200} value={draft.name} onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}/></label>
        <label><span>Owner</span><input required maxLength={120} value={draft.owner} onChange={event => setDraft(current => ({ ...current, owner: event.target.value }))}/></label>
        <label className="case-description"><span>Description</span><textarea maxLength={2000} value={draft.description} onChange={event => setDraft(current => ({ ...current, description: event.target.value }))}/></label>
      </div>
      {createError && <div className="import-error" role="alert"><b>Case could not be created</b><p>{createError}</p></div>}
      <div className="case-create-actions"><Button onClick={closeForm} disabled={creating}>Cancel</Button><Button type="submit" variant="primary" disabled={creating}>{creating ? "Creating…" : "Create case"}</Button></div>
    </form>}
    <div className="case-status-summary" aria-label="Case status summary"><div><b>{items.length}</b><span>Cases</span></div><div><i className="status-dot active"/><b>{items.filter(item => item.status === "active").length}</b><span>Active</span></div></div>
    <div className="table-panel cases-register"><div className="table-toolbar"><div className="search-wrap">⌕<Input placeholder="Search cases…" value={search} onChange={setSearch}/></div><span className="toolbar-spacer"/><Button onClick={() => { setLoading(true); void load(); }}>Refresh</Button></div>
      {loadError && <div className="state-box" role="alert"><strong>Cases could not be loaded</strong><p>{loadError}</p><Button onClick={() => { setLoading(true); void load(); }}>Retry</Button></div>}
      {!loadError && loading && <div className="state-box" aria-live="polite"><strong>Loading persisted cases…</strong></div>}
      {!loadError && !loading && <div className="data-table-wrap"><table className="data-table cases-table"><thead><tr><th>Case</th><th>Type</th><th>Status</th><th>Owner</th><th>Updated (UTC)</th><th/></tr></thead><tbody>{filtered.map(item => <tr key={item.id} onClick={() => navigate(`/cases/${item.id}`)} tabIndex={0} onKeyDown={event => event.key === "Enter" && navigate(`/cases/${item.id}`)}><td><div className="case-cell"><span>B</span><div><strong>{item.name}</strong><small>CASE-{String(item.id).padStart(4, "0")} · {item.description || "No description"}</small></div></div></td><td><span className="type-chip type-batch">Batch</span></td><td><StatusBadge status={item.status}/></td><td>{item.owner}</td><td>{item.updated_at ?? item.created_at}</td><td>›</td></tr>)}</tbody></table>{filtered.length === 0 && <div className="state-box"><span>◇</span><strong>{items.length ? "No matching cases" : "No persisted cases"}</strong><p>{items.length ? "Adjust the search." : "Create a case before importing evidence."}</p>{!items.length && !formOpen && <Button variant="primary" onClick={openForm}>Create case</Button>}</div>}</div>}
      <div className="table-footer"><span>Showing {filtered.length} of {items.length} investigations</span></div></div></>;
}
