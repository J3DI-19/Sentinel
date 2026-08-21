import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImportEvidencePage } from "./ImportEvidencePage";

function choose(name: string, content = "timestamp,value\n1,2") {
  fireEvent.change(screen.getByLabelText("Choose evidence file"), { target: { files: [new File([content], name)] } });
}

describe("ImportEvidencePage", () => {
  it("starts truthfully with no fabricated evidence result", () => {
    render(<ImportEvidencePage />);
    expect(screen.getAllByText("Mock adapter").length).toBeGreaterThan(0);
    expect(screen.getByText(/CSV or JSON · Maximum 50 MiB/)).toBeInTheDocument();
    expect(screen.getByText("No validation result")).toBeInTheDocument();
    expect(screen.queryByText("northbridge-toniot.csv")).not.toBeInTheDocument();
    expect(screen.queryByText("18,420")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Validate with mock adapter/ })).toBeDisabled();
  });

  it("supports keyboard activation and rejects unsupported files accessibly", () => {
    render(<ImportEvidencePage />);
    const dropzone = screen.getByRole("button", { name: /Drop a CSV or JSON/ });
    fireEvent.keyDown(dropzone, { key: "Enter" });
    choose("events.jsonl", "{}");
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a CSV or JSON file");
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(screen.getByRole("button", { name: /Validate with mock adapter/ })).toBeDisabled();
  });

  it("validates, reviews, and completes a mock import", async () => {
    render(<ImportEvidencePage />); choose("valid.CSV");
    fireEvent.click(screen.getByRole("button", { name: /Validate with mock adapter/ }));
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(await screen.findByText(/CSV tabular evidence/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Import with mock adapter/ }));
    await waitFor(() => expect(screen.getByText("Mock import completed. No backend data was written.")).toBeInTheDocument());
  });

  it("cancels processing while preserving the selected file", async () => {
    render(<ImportEvidencePage />); choose("valid.json", "{}");
    fireEvent.click(screen.getByRole("button", { name: /Validate with mock adapter/ }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel processing" }));
    expect(screen.getByText("Processing was cancelled. The selected file is still available.")).toBeInTheDocument();
    expect(screen.getByText("valid.json")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry processing" })).toBeEnabled();
  });

  it("retries a transient mock failure deliberately", async () => {
    render(<ImportEvidencePage />); choose("network-error.json", "{}");
    fireEvent.click(screen.getByRole("button", { name: /Validate with mock adapter/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("The mock adapter simulated a temporary connection failure.");
    fireEvent.click(screen.getByRole("button", { name: "Retry processing" }));
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("The mock adapter simulated a temporary connection failure."));
  });
});
