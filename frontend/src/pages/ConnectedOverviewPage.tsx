import { useEffect, useState } from "react";
import { apiClient } from "../api/batch";
import { normalizeApiError } from "../api/client";
import { Button, EmptyState, PageHeader } from "../components/ui/core";

interface Dashboard {
  case_count: number;
  event_count: number;
  active_cases: number;
  recent_cases: {
    id: number;
    name: string;
    updated_at: string | null;
    created_at: string;
  }[];
}

export function ConnectedOverviewPage({ navigate }: { navigate: (path: string) => void }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void apiClient
      .request<Dashboard>("/dashboard/summary", { signal: controller.signal })
      .then(setData)
      .catch(reason => {
        if (!controller.signal.aborted) {
          setError(normalizeApiError(reason).message);
        }
      });
    return () => controller.abort();
  }, []);

  return (
    <>
      <PageHeader
        eyebrow="Investigation overview · Connected API"
        title="Investigation overview"
        description="Persisted batch workload and evidence activity. Authenticated live capture is available from the Live Monitor."
        actions={
          <Button variant="primary" onClick={() => navigate("/cases")}>
            Open cases
          </Button>
        }
      />

      {error && (
        <div className="state-box" role="alert">
          <strong>Dashboard unavailable</strong>
          <p>{error}</p>
        </div>
      )}

      {!error && !data && (
        <div className="state-box" aria-live="polite">
          <strong>Loading persisted overview…</strong>
        </div>
      )}

      {data && (
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
