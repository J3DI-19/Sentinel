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
});
