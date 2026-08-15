import { ApiClientError } from "../../api/client";
import type { ImportConfiguration, ImportDataSource, ImportStatus, ImportValidationResult, SelectedEvidenceFile } from "./types";

function wait(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException("Aborted", "AbortError")); return; }
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener("abort", () => { window.clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); }, { once: true });
  });
}
function stableCount(name: string): number { return [...name].reduce((total, character) => total + character.charCodeAt(0), 0) % 180 + 20; }

export class MockImportDataSource implements ImportDataSource {
  readonly capability = "mock" as const;
  constructor(private readonly delayMs = 120) {}
  async validate(file: SelectedEvidenceFile, configuration: ImportConfiguration, signal: AbortSignal): Promise<ImportValidationResult> {
    await wait(this.delayMs, signal); const lowerName = file.name.toLowerCase();
    if (lowerName.includes("network-error")) throw new ApiClientError({ code: "mock_network_error", message: "The mock adapter simulated a temporary connection failure.", retryable: true });
    if (lowerName.includes("bad-schema")) throw new ApiClientError({ code: "unsupported_schema", message: "The file does not match an allow-listed evidence schema.", retryable: false });
    const totalRecords = stableCount(file.name);
    const rejectedRecords = lowerName.includes("mixed") ? Math.max(1, Math.floor(totalRecords * 0.08)) : 0;
    const duplicateRecords = lowerName.includes("duplicate") ? Math.max(1, Math.floor(totalRecords * 0.04)) : 0;
    return { validationId: `mock-validation-${stableCount(`${file.name}-${configuration.source}`)}`, detectedSource: configuration.source,
      detectedSchema: file.mediaType === "text/csv" ? "CSV tabular evidence" : "JSON evidence records", totalRecords,
      acceptedRecords: totalRecords - rejectedRecords - duplicateRecords, rejectedRecords, duplicateRecords,
      warnings: duplicateRecords ? ["Previously imported content hashes were detected."] : [],
      problems: rejectedRecords ? [{ scope: "row", code: "mock_invalid_row", message: "Some mock records failed schema validation.", row: 2, correction: "Review the source record before importing." }] : [],
      rejectionLogReference: rejectedRecords ? "mock://rejections/current" : undefined };
  }
  async commit(validationId: string, _configuration: ImportConfiguration, signal: AbortSignal): Promise<ImportStatus> {
    await wait(this.delayMs, signal); return { importId: validationId.replace("validation", "import"), state: "success", progress: { mode: "indeterminate" } };
  }
  async cancel(_importId: string | null, signal: AbortSignal): Promise<void> { await wait(0, signal); }
  async getStatus(importId: string, signal: AbortSignal): Promise<ImportStatus> { await wait(0, signal); return { importId, state: "success", progress: { mode: "indeterminate" } }; }
}
export const importDataSource: ImportDataSource = new MockImportDataSource();
