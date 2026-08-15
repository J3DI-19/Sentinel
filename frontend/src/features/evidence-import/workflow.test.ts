import { describe, expect, it } from "vitest";
import { inspectEvidenceFile } from "./fileValidation";
import { importWorkflowReducer, initialImportWorkflow } from "./workflow";
import type { ImportValidationResult } from "./types";

const file = inspectEvidenceFile(new File(["timestamp,value\n1,2"], "events.csv"));
const validation: ImportValidationResult = { validationId: "validation-1", detectedSource: "generic", detectedSchema: "CSV", totalRecords: 1, acceptedRecords: 1, rejectedRecords: 0, duplicateRecords: 0, warnings: [], problems: [] };

describe("import workflow reducer", () => {
  it("allows only the ordered validate and commit transitions", () => {
    let state = importWorkflowReducer(initialImportWorkflow, { type: "FILE_SELECTED", file });
    state = importWorkflowReducer(state, { type: "UPLOAD_STARTED" });
    state = importWorkflowReducer(state, { type: "VALIDATION_STARTED" });
    state = importWorkflowReducer(state, { type: "VALIDATION_SUCCEEDED", result: validation });
    state = importWorkflowReducer(state, { type: "IMPORT_STARTED" });
    state = importWorkflowReducer(state, { type: "IMPORT_SUCCEEDED", importId: "import-1", partial: false });
    expect(state.state).toBe("success");
    expect(state.importId).toBe("import-1");
  });

  it("clears stale validation when configuration changes", () => {
    const reviewing = { ...initialImportWorkflow, state: "reviewing" as const, file, validation };
    const state = importWorkflowReducer(reviewing, { type: "CONFIGURATION_CHANGED" });
    expect(state.state).toBe("ready");
    expect(state.validation).toBeNull();
  });

  it("preserves the file across cancellation and retry and blocks duplicate starts", () => {
    let state = importWorkflowReducer({ ...initialImportWorkflow, state: "uploading", file }, { type: "UPLOAD_STARTED" });
    expect(state.state).toBe("uploading");
    state = importWorkflowReducer(state, { type: "CANCELLED" });
    expect(state.file).toBe(file);
    state = importWorkflowReducer(state, { type: "RETRY" });
    expect(state.state).toBe("ready");
  });
});
