import { useEffect, useMemo, useState, type FormEvent } from "react";
import { batchApi, type ApiCase } from "../api/batch";
import { normalizeApiError } from "../api/client";
import { Button, EmptyState, Input, PageHeader, StatusBadge } from "../components/ui/core";

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

  const load = (signal?: AbortSignal) =>
    batchApi
      .listCases(signal)
      .then(result => {
        setItems(Array.isArray(result.items) ? result.items : []);
        setLoadError(null);
      })
      .catch(reason => {
        if (!signal?.aborted) setLoadError(normalizeApiError(reason).message);
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false);
      });

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, []);

  const filtered = useMemo(
    () =>
      items.filter(item =>
        (item.name + " " + item.description + " " + item.owner)
          .toLowerCase()
          .includes(search.trim().toLowerCase()),
      ),
    [items, search],
  );

  const openForm = () => {
    setFormOpen(true);
    setCreateError(null);
  };

  const closeForm = () => {
    if (!creating) {
      setFormOpen(false);
      setCreateError(null);
      setDraft(emptyDraft);
    }
  };

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (creating) return;
    const name = draft.name.trim();
    const owner = draft.owner.trim();
    if (!name) {
      setCreateError("Enter a case name.");
      return;
    }
    if (!owner) {
      setCreateError("Enter a case owner.");
      return;
    }
    setCreating(true);
    setCreateError(null);
    try {
      const created = await batchApi.createCase(name, draft.description.trim(), owner);
      setItems(current => [created, ...current.filter(item => item.id !== created.id)]);
      setDraft(emptyDraft);
      setFormOpen(false);
      navigate("/import?case=" + created.id);
    } catch (reason) {
      setCreateError(normalizeApiError(reason).message);
    } finally {
      setCreating(false);
    }
  };

  const refresh = () => {
    setLoading(true);
    void load();
  };

  return (
    <>
      <PageHeader
        eyebrow="Case management · Connected API"
        title="Cases"
        description="Create and open persisted batch investigations."
        actions={
          <Button variant="primary" onClick={openForm} disabled={formOpen}>
            <span className="button-leading-icon" aria-hidden="true">＋</span>
            <span>New case</span>
          </Button>
        }
      />

      {formOpen && (
        <form className="table-panel case-create-panel" aria-label="Create case" onSubmit={create}>
          <header className="case-create-header">
            <span className="case-create-header__icon" aria-hidden="true">＋</span>
            <div>
              <span className="eyebrow">New persisted investigation</span>
              <h2>Create case</h2>
              <p>Define the investigation before importing evidence.</p>
            </div>
          </header>

          <div className="case-create-fields">
            <label>
              <span>Case name</span>
              <input
                autoFocus
                required
                maxLength={200}
                placeholder="e.g. North facility review"
                value={draft.name}
                onChange={event => setDraft(current => ({ ...current, name: event.target.value }))}
              />
            </label>
            <label>
              <span>Owner</span>
              <input
                required
                maxLength={120}
                value={draft.owner}
                onChange={event => setDraft(current => ({ ...current, owner: event.target.value }))}
              />
            </label>
            <label className="case-description">
              <span>Description <small aria-hidden="true">Optional</small></span>
              <textarea
                aria-label="Description"
                maxLength={2000}
                placeholder="Add the investigation scope or context."
                value={draft.description}
                onChange={event => setDraft(current => ({ ...current, description: event.target.value }))}
              />
            </label>
          </div>

          {createError && (
            <div className="import-error case-create-error" role="alert">
              <b>Case could not be created</b>
              <p>{createError}</p>
            </div>
          )}

          <footer className="case-create-actions">
            <Button onClick={closeForm} disabled={creating}>Cancel</Button>
            <Button type="submit" variant="primary" disabled={creating}>
              {creating ? "Creating…" : "Create case"}
            </Button>
          </footer>
        </form>
      )}

      <div className="case-status-summary" aria-label="Case status summary">
        <div><b>{items.length}</b><span>Cases</span></div>
        <div>
          <i className="status-dot active" />
          <b>{items.filter(item => item.status === "active").length}</b>
          <span>Active</span>
        </div>
      </div>

      <section className="table-panel cases-register" aria-label="Persisted cases">
        <div className="table-toolbar">
          <div className="search-wrap cases-search">
            <span className="cases-search__icon" aria-hidden="true">⌕</span>
            <Input
              ariaLabel="Search cases"
              placeholder="Search cases…"
              value={search}
              onChange={setSearch}
            />
          </div>
          <span className="toolbar-spacer" />
          <Button onClick={refresh} disabled={loading}>Refresh</Button>
        </div>

        {loadError && (
          <div className="state-box" role="alert">
            <strong>Cases could not be loaded</strong>
            <p>{loadError}</p>
            <Button onClick={refresh}>Retry</Button>
          </div>
        )}

        {!loadError && loading && (
          <div className="state-box" aria-live="polite">
            <strong>Loading persisted cases…</strong>
          </div>
        )}

        {!loadError && !loading && filtered.length > 0 && (
          <div className="data-table-wrap">
            <table className="data-table cases-table">
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Type</th>
                  <th scope="col">Status</th>
                  <th scope="col">Owner</th>
                  <th scope="col">Updated (UTC)</th>
                  <th scope="col" aria-label="Open case" />
                </tr>
              </thead>
              <tbody>
                {filtered.map(item => {
                  const updatedAt = item.updated_at ?? item.created_at;
                  return (
                    <tr
                      key={item.id}
                      onClick={() => navigate("/cases/" + item.id)}
                      tabIndex={0}
                      onKeyDown={event => event.key === "Enter" && navigate("/cases/" + item.id)}
                    >
                      <td>
                        <div className="case-cell">
                          <span>B</span>
                          <div>
                            <strong>{item.name}</strong>
                            <small>
                              CASE-{String(item.id).padStart(4, "0")} · {item.description || "No description"}
                            </small>
                          </div>
                        </div>
                      </td>
                      <td><span className="type-chip type-batch">Batch</span></td>
                      <td><StatusBadge status={item.status} /></td>
                      <td>{item.owner}</td>
                      <td><time dateTime={updatedAt}>{updatedAt}</time></td>
                      <td aria-hidden="true">›</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {!loadError && !loading && filtered.length === 0 && (
          <EmptyState
            title={items.length ? "No matching cases" : "No persisted cases"}
            description={items.length ? "Try a different name, owner, or description." : "Create a case before importing evidence."}
            action={
              items.length
                ? <Button onClick={() => setSearch("")}>Clear search</Button>
                : !formOpen && <Button variant="primary" onClick={openForm}>Create case</Button>
            }
          />
        )}

        <div className="table-footer">
          <span>Showing {filtered.length} of {items.length} investigations</span>
        </div>
      </section>
    </>
  );
}
