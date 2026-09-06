import { useEffect, useState } from "react";
import { investigationApi, type DashboardSummary } from "../api/investigation";
import { normalizeApiError } from "../api/client";
import { Button, EmptyState, PageHeader } from "../components/ui/core";

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
      .catch(reason => {
        if (!controller.signal.aborted) setError(normalizeApiError(reason).message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [requestId]);

  const reload = () => setRequestId(value => value + 1);

  return (
    <>
      <PageHeader
        eyebrow="Investigation overview · Connected API"
        title="Investigation overview"
        description="Persisted batch workload and evidence activity. Authenticated live capture is available from the Live Monitor."
        actions={<><Button onClick={reload} disabled={loading}>Refresh</Button><Button variant="primary" onClick={() => navigate("/cases")}>Open cases</Button></>}
      />

      {error && (
        <div className="state-box" role="alert">
          <strong>Dashboard unavailable</strong>
          <p>{error}</p>
          <Button onClick={reload} disabled={loading}>Retry</Button>
        </div>
      )}

      {!error && loading && (
        <div className="state-box" aria-live="polite">
          <strong>Loading persisted overview…</strong>
        </div>
      )}

      {!loading && data && (
        <>
          <div className="case-status-summary">
            <div>
              <b>{data.case_count}</b>
              <span>Persisted cases</span>
            </div>
            <div>
              <b>{data.active_cases}</b>
              <span>Active cases</span>
            </div>
            <div>
              <b>{data.event_count}</b>
              <span>Canonical events</span>
            </div>
          </div>

          <section className="table-panel" aria-labelledby="recent-cases-heading">
            <div className="panel-head">
              <div>
                <span className="eyebrow">Case activity</span>
                <h2 id="recent-cases-heading">Recent persisted cases</h2>
                <p>Your most recently updated batch investigations.</p>
              </div>
            </div>

            {data.recent_cases.length ? (
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Case</th>
                      <th scope="col">Updated (UTC)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_cases.map(item => {
                      const updatedAt = item.updated_at ?? item.created_at;
                      return (
                        <tr key={item.id}>
                          <td>
                            <button
                              className="overview-case-link"
                              type="button"
                              onClick={() => navigate("/cases/" + item.id + "/overview")}
                            >
                              {item.name}
                            </button>
                          </td>
                          <td>
                            <time dateTime={updatedAt}>{updatedAt}</time>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                title="No persisted cases"
                description="Create a case to begin a batch investigation and import evidence."
                action={<Button variant="primary" onClick={() => navigate("/cases")}>Create case</Button>}
              />
            )}
          </section>
        </>
      )}
    </>
  );
}
