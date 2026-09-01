export type EvidenceSource = "casas_smart_home" | "ton_iot_fridge_telemetry" | "simulated" | "generic";

export type LocalFileValidation =
  | { status: "valid" }
  | { status: "invalid"; code: "empty_file" | "unsupported_type" | "file_too_large"; message: string };

export interface SelectedEvidenceFile {
  file: File;
  name: string;
  mediaType: "text/csv" | "application/json";
  sizeBytes: number;
  validation: LocalFileValidation;
}

export interface ImportConfiguration {
  caseId: string;
  source: EvidenceSource;
  timezone: string;
  timestampField: string;
  duplicatePolicy: "skip_exact_hashes";
  label?: string;
}

export interface ImportProblem {
  scope: "file" | "column" | "row";
  code: string;
  message: string;
  row?: number;
  column?: string;
  correction?: string;
}

export interface ImportValidationResult {
  validationId: string;
  detectedSource: EvidenceSource;
  detectedSchema: string;
  totalRecords: number;
  acceptedRecords: number;
  rejectedRecords: number;
  duplicateRecords: number;
  warnings: string[];
  problems: ImportProblem[];
  rejectionLogReference?: string;
}

export type ImportWorkflowState =
  | "idle" | "selecting" | "ready" | "uploading" | "validating"
  | "reviewing" | "importing" | "success" | "partial-success"
  | "cancelled" | "failed";

export interface ImportStatus {
  importId: string;
  state: ImportWorkflowState;
  progress: { mode: "indeterminate" } | { mode: "determinate"; percent: number };
  result?: ImportValidationResult;
  error?: ImportDataError;
}

export interface ImportDataError {
  code: string;
  message: string;
  retryable: boolean;
  status?: number;
  requestId?: string;
  details?: unknown;
}

export interface ImportDataSource {
  readonly capability: "mock" | "backend";
  validate(file: SelectedEvidenceFile, configuration: ImportConfiguration, signal: AbortSignal): Promise<ImportValidationResult>;
  commit(validationId: string, configuration: ImportConfiguration, signal: AbortSignal): Promise<ImportStatus>;
  cancel(importId: string | null, signal: AbortSignal): Promise<void>;
  getStatus(importId: string, signal: AbortSignal): Promise<ImportStatus>;
}
