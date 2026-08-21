import type { ImportDataError, ImportValidationResult, ImportWorkflowState, SelectedEvidenceFile } from "./types";

export interface ImportWorkflow {
  state: ImportWorkflowState;
  file: SelectedEvidenceFile | null;
  validation: ImportValidationResult | null;
  importId: string | null;
  error: ImportDataError | null;
}

export const initialImportWorkflow: ImportWorkflow = { state: "idle", file: null, validation: null, importId: null, error: null };

export type ImportWorkflowEvent =
  | { type: "SELECTING" } | { type: "FILE_SELECTED"; file: SelectedEvidenceFile }
  | { type: "FILE_REJECTED"; file: SelectedEvidenceFile; error: ImportDataError }
  | { type: "REMOVE_FILE" } | { type: "CONFIGURATION_CHANGED" }
  | { type: "UPLOAD_STARTED" } | { type: "VALIDATION_STARTED" }
  | { type: "VALIDATION_SUCCEEDED"; result: ImportValidationResult }
  | { type: "IMPORT_STARTED" } | { type: "IMPORT_SUCCEEDED"; importId: string; partial: boolean }
  | { type: "FAILED"; error: ImportDataError } | { type: "CANCELLED" } | { type: "RETRY" };

export function importWorkflowReducer(state: ImportWorkflow, event: ImportWorkflowEvent): ImportWorkflow {
  switch (event.type) {
    case "SELECTING": return ["uploading", "validating", "importing"].includes(state.state) ? state : { ...state, state: "selecting", error: null };
    case "FILE_SELECTED": return { state: "ready", file: event.file, validation: null, importId: null, error: null };
    case "FILE_REJECTED": return { state: "failed", file: event.file, validation: null, importId: null, error: event.error };
    case "REMOVE_FILE": return initialImportWorkflow;
    case "CONFIGURATION_CHANGED":
      if (!state.file) return state;
      return { ...state, state: state.file.validation.status === "valid" ? "ready" : "failed", validation: null, importId: null, error: state.file.validation.status === "valid" ? null : state.error };
    case "UPLOAD_STARTED": return state.file?.validation.status === "valid" && !["uploading", "validating", "importing"].includes(state.state) ? { ...state, state: "uploading", error: null } : state;
    case "VALIDATION_STARTED": return state.state === "uploading" ? { ...state, state: "validating" } : state;
    case "VALIDATION_SUCCEEDED": return state.state === "validating" ? { ...state, state: "reviewing", validation: event.result, error: null } : state;
    case "IMPORT_STARTED": return state.state === "reviewing" ? { ...state, state: "importing", error: null } : state;
    case "IMPORT_SUCCEEDED": return state.state === "importing" ? { ...state, state: event.partial ? "partial-success" : "success", importId: event.importId } : state;
    case "FAILED": return { ...state, state: "failed", error: event.error };
    case "CANCELLED": return ["uploading", "validating", "importing"].includes(state.state) ? { ...state, state: "cancelled", error: null } : state;
    case "RETRY": return state.file?.validation.status === "valid" && (state.state === "failed" || state.state === "cancelled") ? { ...state, state: "ready", validation: null, importId: null, error: null } : state;
  }
}
