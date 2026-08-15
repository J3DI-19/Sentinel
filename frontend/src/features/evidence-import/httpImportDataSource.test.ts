import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../../api/client";
import { inspectEvidenceFile } from "./fileValidation";
import { HttpImportDataSource } from "./httpImportDataSource";
import type { ImportConfiguration } from "./types";

const configuration: ImportConfiguration = { caseId: "7", source: "simulation", timezone: "UTC", timestampField: "auto", duplicatePolicy: "skip_exact_hashes" };
const report = { metadata: { evidence_id: "evidence-1", source_type: "simulation", dataset_profile: "simulation@1.0" }, total_records: 2, accepted_records: 1, rejected_records: 1, issues: [{ level: "error", code: "INVALID_TIMESTAMP", message: "Invalid timestamp", row_number: 3, field: "timestamp" }] };
const job = (state: string, validation: typeof report | null = report) => ({ import_id: "import-1", state, validation, error: null });

function adapter(...responses: unknown[]) {
  const request = vi.fn(); responses.forEach(response => request.mockResolvedValueOnce(response));
  return { source: new HttpImportDataSource({ request } as unknown as ApiClient, 0), request };
}

describe("HTTP import data source", () => {
  it("maps validation problems and explicitly approves a partial commit", async () => {
    const { source, request } = adapter(job("awaiting_commit"), job("partial_success"));
    const result = await source.validate(inspectEvidenceFile(new File(["data"], "events.csv")), configuration, new AbortController().signal);
    expect(result).toMatchObject({ acceptedRecords: 1, rejectedRecords: 1, detectedSchema: "simulation@1.0" });
    expect(result.problems[0]).toMatchObject({ scope: "row", code: "INVALID_TIMESTAMP", row: 3 });
    await expect(source.commit(result.validationId, configuration, new AbortController().signal)).resolves.toMatchObject({ state: "partial-success" });
    expect(JSON.parse(request.mock.calls[1][1].body)).toEqual({ allow_partial: true });
  });

  it("represents duplicate evidence without fabricated accepted counts", async () => {
    const { source } = adapter(job("duplicate", null));
    await expect(source.validate(inspectEvidenceFile(new File(["data"], "events.json")), configuration, new AbortController().signal)).resolves.toMatchObject({ duplicateRecords: 1, acceptedRecords: 0 });
  });

  it("rejects upload until a persisted case is selected", async () => {
    const { source, request } = adapter();
    await expect(source.validate(inspectEvidenceFile(new File(["data"], "events.csv")), { ...configuration, caseId: "" }, new AbortController().signal)).rejects.toMatchObject({ code: "case_required", retryable: false });
    expect(request).not.toHaveBeenCalled();
  });
});
