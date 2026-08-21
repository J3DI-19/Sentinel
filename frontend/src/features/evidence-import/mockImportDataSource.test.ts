import { describe, expect, it } from "vitest";
import { inspectEvidenceFile } from "./fileValidation";
import { MockImportDataSource } from "./mockImportDataSource";
import type { ImportConfiguration } from "./types";

const configuration: ImportConfiguration = { caseId: "demo", source: "generic", timezone: "UTC", timestampField: "auto", duplicatePolicy: "skip_exact_hashes" };
const signal = () => new AbortController().signal;

describe("mock import data source contract", () => {
  const source = new MockImportDataSource(0);
  it("returns deterministic success and commit results", async () => {
    const file = inspectEvidenceFile(new File(["a,b\n1,2"], "valid.csv"));
    const first = await source.validate(file, configuration, signal());
    const second = await source.validate(file, configuration, signal());
    expect(second).toEqual(first);
    expect((await source.commit(first.validationId, configuration, signal())).state).toBe("success");
  });
  it("models partial, duplicate, retryable, and terminal scenarios", async () => {
    expect((await source.validate(inspectEvidenceFile(new File(["{}"], "mixed.json")), configuration, signal())).rejectedRecords).toBeGreaterThan(0);
    expect((await source.validate(inspectEvidenceFile(new File(["{}"], "duplicate.json")), configuration, signal())).duplicateRecords).toBeGreaterThan(0);
    await expect(source.validate(inspectEvidenceFile(new File(["{}"], "network-error.json")), configuration, signal())).rejects.toMatchObject({ retryable: true });
    await expect(source.validate(inspectEvidenceFile(new File(["{}"], "bad-schema.json")), configuration, signal())).rejects.toMatchObject({ retryable: false });
  });
  it("honors cancellation", async () => {
    const controller = new AbortController(); controller.abort();
    await expect(source.validate(inspectEvidenceFile(new File(["{}"], "valid.json")), configuration, controller.signal)).rejects.toMatchObject({ name: "AbortError" });
  });
});
