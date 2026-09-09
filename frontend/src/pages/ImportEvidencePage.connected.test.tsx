import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ImportDataSource } from "../features/evidence-import/types";
import { ImportEvidencePage } from "./ImportEvidencePage";

const cases = [
  { id: 2, name: "Newest", description: "", case_type: "batch", status: "active", owner: "Investigator", created_at: "2026-09-01T00:00:00Z", updated_at: "2026-09-01T00:00:00Z" },
  { id: 1, name: "Older", description: "", case_type: "batch", status: "active", owner: "Investigator", created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z" },
];
const dataSource: ImportDataSource = { capability: "backend", validate: vi.fn(), commit: vi.fn(), cancel: vi.fn(async () => {}), getStatus: vi.fn() };

describe("connected ImportEvidencePage case selection", () => {
  beforeEach(() => { vi.restoreAllMocks(); vi.mocked(dataSource.validate).mockReset(); vi.mocked(dataSource.commit).mockReset(); });
  const respond = (items = cases) => vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ items, page: 1, page_size: 100, total: items.length }), { status: 200 }))));

  it("selects the exact requested persisted case", async () => {
    respond();
    render(<ImportEvidencePage search="?case=1" navigate={vi.fn()} dataSource={dataSource}/>);
    await waitFor(() => expect(screen.getByLabelText("Case destination")).toHaveValue("1"));
    expect(screen.queryByText("Case selection required")).not.toBeInTheDocument();
  });

  it("defaults to the most recently updated case when no ID is requested", async () => {
    respond();
    render(<ImportEvidencePage navigate={vi.fn()} dataSource={dataSource}/>);
    await waitFor(() => expect(screen.getByLabelText("Case destination")).toHaveValue("2"));
  });

  it("does not fall back for stale or malformed requested IDs", async () => {
    respond();
    const { rerender } = render(<ImportEvidencePage search="?case=999" navigate={vi.fn()} dataSource={dataSource}/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("no longer available");
    expect(screen.getByLabelText("Case destination")).toHaveValue("");
    rerender(<ImportEvidencePage search="?case=bad" navigate={vi.fn()} dataSource={dataSource}/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("case ID is invalid");
    expect(screen.getByLabelText("Case destination")).toHaveValue("");
  });

  it("separates no-case and load-failure recovery states", async () => {
    respond([]);
    const navigate = vi.fn();
    const { unmount } = render(<ImportEvidencePage navigate={navigate} dataSource={dataSource}/>);
    expect(await screen.findByText("No persisted cases")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Cases" }));
    expect(navigate).toHaveBeenCalledWith("/cases");
    unmount();

    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ code: "database_unavailable", message: "The evidence database is unavailable.", retryable: true }), { status: 503, headers: { "Content-Type": "application/json" } }))));
    render(<ImportEvidencePage navigate={vi.fn()} dataSource={dataSource}/>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cases could not be loaded");
    expect(screen.getByRole("alert")).toHaveTextContent("evidence database is unavailable");
  });

  it("documents the selected profile and offers the synthetic example", async () => {
    respond();
    render(<ImportEvidencePage navigate={vi.fn()} dataSource={dataSource}/>);
    await screen.findByLabelText("Case destination");
    expect(screen.getByText("ton_iot_fridge_telemetry@1.0")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Simulation/ }));
    expect(screen.getByText("simulated@1.0")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download synthetic example CSV" })).toHaveAttribute("href", "/examples/simulated-evidence.csv");
    expect(screen.queryByRole("button", { name: "View import history" })).not.toBeInTheDocument();
  });

  it("offers blind HAI and IoT-23 profiles with label-leakage guidance", async () => {
    respond();
    render(<ImportEvidencePage navigate={vi.fn()} dataSource={dataSource}/>);
    await screen.findByLabelText("Case destination");
    fireEvent.click(screen.getByRole("button", { name: /HAI ICS · Blind/ }));
    expect(screen.getByText("hai_ics_blind@1.0")).toBeInTheDocument();
    expect(screen.getByText("Blind analysis · labels prohibited")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /real label-free HAI sample/ })).toHaveAttribute("href", "/examples/hai-ics-blind-sample.csv");
    fireEvent.click(screen.getByRole("button", { name: /IoT-23 · Blind/ }));
    expect(screen.getByText("iot23_zeek_blind@1.0")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /real label-free IoT-23 sample/ })).toHaveAttribute("href", "/examples/iot23-zeek-blind-sample.csv");
  });

  it("requires partial approval, renders row and field context, prevents duplicate requests, and opens results", async () => {
    respond(); const navigate = vi.fn();
    let finishValidation!: (value: Awaited<ReturnType<ImportDataSource["validate"]>>) => void;
    vi.mocked(dataSource.validate).mockImplementation(() => new Promise(resolve => { finishValidation = resolve; }));
    vi.mocked(dataSource.commit).mockResolvedValue({ importId: "import-1", state: "partial-success", progress: { mode: "indeterminate" } });
    render(<ImportEvidencePage search="?case=1" navigate={navigate} dataSource={dataSource}/>);
    await waitFor(() => expect(screen.getByLabelText("Case destination")).toHaveValue("1"));
    fireEvent.change(screen.getByLabelText("Choose evidence file"), { target: { files: [new File(["data"], "events.csv")] } });
    const validate = screen.getByRole("button", { name: /Validate with backend/ });
    fireEvent.click(validate); fireEvent.click(validate);
    expect(dataSource.validate).toHaveBeenCalledTimes(1);
    finishValidation({ validationId: "import-1", detectedSource: "simulated", detectedSchema: "simulated@1.0", totalRecords: 2, acceptedRecords: 1, rejectedRecords: 1, duplicateRecords: 0, warnings: ["One row was rejected."], problems: [{ scope: "row", code: "INVALID_TIMESTAMP", message: "Invalid timestamp", row: 3, column: "timestamp", correction: "Use an ISO timestamp." }] });
    expect(await screen.findByText("Row 3 · Field timestamp")).toBeInTheDocument();
    const commit = screen.getByRole("button", { name: "Approve partial import →" });
    expect(commit).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(commit); fireEvent.click(commit);
    await waitFor(() => expect(dataSource.commit).toHaveBeenCalledTimes(1));
    fireEvent.click(await screen.findByRole("button", { name: "Open case results →" }));
    expect(navigate).toHaveBeenCalledWith("/cases/1/overview");
  });
});
