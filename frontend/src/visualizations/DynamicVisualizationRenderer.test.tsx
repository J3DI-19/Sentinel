import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DynamicVisualizationRenderer } from "./DynamicVisualizationRenderer";

describe("DynamicVisualizationRenderer", () => {
  it("fails safely for component types outside the allow-list", () => {
    render(<DynamicVisualizationRenderer specification={{ id: "unsafe", name: "Unsafe", description: "", evidenceRefs: [], components: [{ id: "x", type: "generated-react-component", title: "Unknown", dataRef: "incident-risk" }] }}/>);
    expect(screen.getByText("Visualization unavailable")).toBeInTheDocument();
    expect(screen.getByText(/not in the approved registry/i)).toBeInTheDocument();
  });

  it("fails safely when a deterministic data reference is missing", () => {
    render(<DynamicVisualizationRenderer specification={{ id: "missing", name: "Missing", description: "", evidenceRefs: [], components: [{ id: "x", type: "metric-card", title: "Missing", dataRef: "does-not-exist" }] }}/>);
    expect(screen.getByText(/could not be resolved/i)).toBeInTheDocument();
  });

  it("renders an allow-listed production dataset supplied by the backend", () => {
    render(<DynamicVisualizationRenderer datasets={{ alerts: [{ id: "a-1", time: "2026-09-10T10:00:00Z", title: "Persisted alert", severity: "High", risk: 81, status: "pending" }] }} specification={{ id: "safe", name: "Safe", description: "", evidenceRefs: [], components: [{ id: "alerts", type: "alert_list", title: "Alerts", dataRef: "alerts" }] }}/>);
    expect(screen.getByText("Persisted alert")).toBeInTheDocument();
    expect(screen.getByText(/81 risk/i)).toBeInTheDocument();
  });
});
