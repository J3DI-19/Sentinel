import { ApiClient, ApiClientError } from "../../api/client";
import type { components } from "../../api/generated";
import type { EvidenceSource, ImportConfiguration, ImportDataSource, ImportStatus, ImportValidationResult, SelectedEvidenceFile } from "./types";

interface ApiIssue { level: string; code: string; message: string; row_number: number | null; field: string | null }
interface ApiValidation {
  metadata: { evidence_id: string; source_type: EvidenceSource; dataset_profile: string };
  total_records: number; accepted_records: number; rejected_records: number; issues: ApiIssue[];
}
type GeneratedImport = components["schemas"]["ImportPublic"];
type ApiImport = Omit<GeneratedImport, "validation" | "error"> & {
  validation: ApiValidation | null;
  error: { code: string; message: string; retryable: boolean } | null;
};

const terminal = new Set(["awaiting_commit", "duplicate", "rejected", "failed", "cancelled", "completed", "partial_success"]);

export class HttpImportDataSource implements ImportDataSource {
  readonly capability = "backend" as const;
  private readonly client: ApiClient;
  private activeImportId: string | null = null;
  private validations = new Map<string, ImportValidationResult>();

  constructor(client = new ApiClient("/api/v1"), private readonly pollIntervalMs = 750) { this.client = client; }

  async validate(file: SelectedEvidenceFile, configuration: ImportConfiguration, signal: AbortSignal): Promise<ImportValidationResult> {
    const caseId = Number(configuration.caseId);
    if (!Number.isInteger(caseId) || caseId < 1) throw new ApiClientError({ code: "case_required", message: "Choose a persisted case before validating evidence.", retryable: false });
    const body = new FormData();
    body.set("file", file.file, file.name); body.set("source_type", configuration.source);
    body.set("timezone", configuration.timezone); body.set("timestamp_field", configuration.timestampField);
    body.set("duplicate_policy", configuration.duplicatePolicy);
    if (configuration.label) body.set("label", configuration.label);
    let job = await this.client.request<ApiImport>(`/cases/${caseId}/imports`, { method: "POST", body, signal });
    this.activeImportId = job.import_id;
    job = await this.poll(job, signal);
    if (job.state === "failed") throw this.jobError(job);
    if (job.state === "cancelled") throw new DOMException("Import cancelled", "AbortError");
    const result = this.mapValidation(job, configuration.source);
    this.validations.set(job.import_id, result);
    return result;
  }

  async commit(validationId: string, _configuration: ImportConfiguration, signal: AbortSignal): Promise<ImportStatus> {
    const validation = this.validations.get(validationId);
    let job = await this.client.request<ApiImport>(`/imports/${validationId}/commit`, {
      method: "POST", signal, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ allow_partial: Boolean(validation?.rejectedRecords) }),
    });
    job = await this.poll(job, signal);
    if (job.state === "failed" || job.state === "rejected") throw this.jobError(job);
    return this.mapStatus(job);
  }

  async cancel(importId: string | null, signal: AbortSignal): Promise<void> {
    const id = importId ?? this.activeImportId; if (!id) return;
    await this.client.request<ApiImport>(`/imports/${id}/cancel`, { method: "POST", signal });
  }

  async getStatus(importId: string, signal: AbortSignal): Promise<ImportStatus> {
    return this.mapStatus(await this.client.request<ApiImport>(`/imports/${importId}`, { signal }));
  }

  private async poll(initial: ApiImport, signal: AbortSignal): Promise<ApiImport> {
    let job = initial;
    while (!terminal.has(job.state)) {
      await new Promise<void>((resolve, reject) => {
        const timer = window.setTimeout(resolve, this.pollIntervalMs);
        signal.addEventListener("abort", () => { window.clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); }, { once: true });
      });
      job = await this.client.request<ApiImport>(`/imports/${job.import_id}`, { signal });
    }
    return job;
  }

  private mapValidation(job: ApiImport, source: EvidenceSource): ImportValidationResult {
    if (!job.validation) return { validationId: job.import_id, detectedSource: source, detectedSchema: "Exact same-case evidence hash", totalRecords: 0, acceptedRecords: 0, rejectedRecords: 0, duplicateRecords: 1, warnings: ["This evidence is already associated with the selected case."], problems: [] };
    return {
      validationId: job.import_id, detectedSource: job.validation.metadata.source_type,
      detectedSchema: job.validation.metadata.dataset_profile, totalRecords: job.validation.total_records,
      acceptedRecords: job.validation.accepted_records, rejectedRecords: job.validation.rejected_records,
      duplicateRecords: 0,
      warnings: job.validation.issues.filter(issue => issue.level === "warning").map(issue => issue.message),
      problems: job.validation.issues.filter(issue => issue.level === "error").map(issue => ({ scope: issue.row_number ? "row" : issue.field ? "column" : "file", code: issue.code, message: issue.message, row: issue.row_number ?? undefined, column: issue.field ?? undefined })),
    };
  }

  private mapStatus(job: ApiImport): ImportStatus {
    const state = job.state === "completed" ? "success" : job.state === "partial_success" || job.state === "duplicate" ? "partial-success" : job.state === "cancelled" ? "cancelled" : job.state === "failed" || job.state === "rejected" ? "failed" : job.state === "awaiting_commit" ? "reviewing" : job.state === "normalizing" || job.state === "analyzing" ? "importing" : "validating";
    return { importId: job.import_id, state, progress: { mode: "indeterminate" }, error: job.error ?? undefined };
  }

  private jobError(job: ApiImport): ApiClientError {
    return new ApiClientError(job.error ?? { code: job.state === "rejected" ? "evidence_rejected" : "import_failed", message: job.state === "rejected" ? "The file schema was fully rejected." : "The import job failed.", retryable: false });
  }
}
