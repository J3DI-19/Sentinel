import { useEffect, useState } from "react";
import { normalizeApiError } from "../api/client";
import { investigationApi, type DashboardSummary } from "../api/investigation";
import { Button, PageHeader } from "../components/ui/core";

export function ConnectedOverviewPage({ navigate }: { navigate: (path: string) => void }) {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestId, setRequestId] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    void investigationApi.dashboard(controller.signal)
      .then(setData)
      .catch(reason => { if (!controller.signal.aborted) setError(normalizeApiError(reason).message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [requestId]);

  const reload = () => setRequestId(value => value + 1);

  return <>
    <PageHeader
      eyebrow="Investigation overview · Connected API"
      title="Investigation overview"
      description="Persisted batch workload and evidence activity. Genuine live ingestion and real-time delivery remain Steps 5 and 7."
      actions={<><Button onClick={reload} disabled={loading}>Refresh</Button><Button variant="primary" onClick={() => navigate("/cases")}>Open cases</Button></>}
    />
    {error && <div className="state-box" role="alert"><strong>Dashboard unavailable</strong><p>{error}</p><Button onClick={reload} disabled={loading}>Retry</Button></div>}
    {!error && loading && <div className="state-box" aria-live="polite"><strong>Loading persisted overview…</strong></div>}
    {!loading && data && <><div className="case-status-summary"><div><b>{data.case_count}</b><span>Persisted cases</span></div><div><b>{data.active_cases}</b><span>Active cases</span></div><div><b>{data.event_count}</b><span>Canonical events</span></div></div><div className="table-panel"><h2>Recent persisted cases</h2>{data.recent_cases.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Case</th><th>Updated (UTC)</th></tr></thead><tbody>{data.recent_cases.map(item => <tr key={item.id} onClick={() => navigate(`/cases/${item.id}/overview`)}><td>{item.name}</td><td>{item.updated_at ?? item.created_at}</td></tr>)}</tbody></table></div> : <div className="state-box"><span>◇</span><strong>No persisted cases</strong><p>Create a case to begin the batch investigation journey.</p></div>}</div></>}
  </>;
}
