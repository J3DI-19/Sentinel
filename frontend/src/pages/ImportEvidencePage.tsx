import { useEffect, useReducer, useRef, useState } from "react";
import { normalizeApiError } from "../api/client";
import { batchApi, type ApiCase } from "../api/batch";
import { Button, PageHeader } from "../components/ui/core";
import { EvidenceFileIntake, EvidenceSourcePicker, ImportActions, ImportConfigurationPanel, ValidationSummary, WorkflowStatus } from "../features/evidence-import/components";
import { inspectEvidenceFile } from "../features/evidence-import/fileValidation";
import { importDataSource } from "../features/evidence-import/importDataSource";
import type { EvidenceSource, ImportConfiguration } from "../features/evidence-import/types";
import { importWorkflowReducer, initialImportWorkflow } from "../features/evidence-import/workflow";
import "../import-workflow.css";

const initialConfiguration: ImportConfiguration = { caseId: importDataSource.capability === "mock" ? "demo-case" : "", source: "ton_iot_telemetry", timezone: "UTC", timestampField: "auto", duplicatePolicy: "skip_exact_hashes", label: "" };

export function ImportEvidencePage() {
  const [workflow, dispatch] = useReducer(importWorkflowReducer, initialImportWorkflow);
  const [configuration, setConfiguration] = useState(initialConfiguration);
  const [dragActive, setDragActive] = useState(false);
  const [caseOptions, setCaseOptions] = useState<ApiCase[]>([]);
  const [caseError, setCaseError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const operationRef = useRef<AbortController | null>(null);
  const busy = ["uploading", "validating", "importing"].includes(workflow.state);

  useEffect(() => { if (workflow.state === "failed") errorRef.current?.focus(); }, [workflow.state]);
  useEffect(() => () => operationRef.current?.abort(), []);
  useEffect(() => {
    if (importDataSource.capability === "mock") return;
    const controller = new AbortController();
    void batchApi.listCases(controller.signal).then(result => {
      setCaseOptions(result.items);
      if (result.items[0]) setConfiguration(current => current.caseId ? current : { ...current, caseId: String(result.items[0].id) });
    }).catch(error => { if (!controller.signal.aborted) setCaseError(normalizeApiError(error).message); });
    return () => controller.abort();
  }, []);

  const chooseFile = () => { dispatch({ type: "SELECTING" }); inputRef.current?.click(); };
  const selectFile = (file: File) => {
    const selected = inspectEvidenceFile(file);
    if (selected.validation.status === "invalid") dispatch({ type: "FILE_REJECTED", file: selected, error: { code: selected.validation.code, message: selected.validation.message, retryable: false } });
    else dispatch({ type: "FILE_SELECTED", file: selected });
  };
  const updateConfiguration = (next: ImportConfiguration) => { setConfiguration(next); dispatch({ type: "CONFIGURATION_CHANGED" }); };
  const updateSource = (source: EvidenceSource) => updateConfiguration({ ...configuration, source });

  const validate = async () => {
    if (!workflow.file || busy) return;
    const controller = new AbortController(); operationRef.current = controller;
    dispatch({ type: "UPLOAD_STARTED" }); dispatch({ type: "VALIDATION_STARTED" });
    try { const result = await importDataSource.validate(workflow.file, configuration, controller.signal); dispatch({ type: "VALIDATION_SUCCEEDED", result }); }
    catch (error) { if (!controller.signal.aborted) dispatch({ type: "FAILED", error: normalizeApiError(error) }); }
    finally { if (operationRef.current === controller) operationRef.current = null; }
  };
  const commit = async () => {
    if (!workflow.validation || busy) return;
    const controller = new AbortController(); operationRef.current = controller; dispatch({ type: "IMPORT_STARTED" });
    try { const status = await importDataSource.commit(workflow.validation.validationId, configuration, controller.signal); dispatch({ type: "IMPORT_SUCCEEDED", importId: status.importId, partial: workflow.validation.rejectedRecords > 0 || workflow.validation.duplicateRecords > 0 }); }
    catch (error) { if (!controller.signal.aborted) dispatch({ type: "FAILED", error: normalizeApiError(error) }); }
    finally { if (operationRef.current === controller) operationRef.current = null; }
  };
  const cancel = () => { operationRef.current?.abort(); operationRef.current = null; dispatch({ type: "CANCELLED" }); void importDataSource.cancel(workflow.importId, new AbortController().signal); };
  const retry = () => { dispatch({ type: "RETRY" }); void validate(); };
  const completedSteps = workflow.state === "idle" || workflow.state === "selecting" ? 1 : workflow.state === "ready" || workflow.state === "uploading" || workflow.state === "validating" || workflow.state === "failed" || workflow.state === "cancelled" ? 2 : workflow.state === "reviewing" || workflow.state === "importing" ? 3 : 4;

  const capabilityLabel = importDataSource.capability === "mock" ? "Mock adapter" : "Connected API";
  return <><PageHeader eyebrow={`Evidence intake · ${capabilityLabel}`} title="Import evidence" description={importDataSource.capability === "mock" ? "Prepare CSV or JSON evidence without backend persistence." : "Validate evidence first, then explicitly commit accepted records to the selected case."} actions={<><span className="capability-chip">{capabilityLabel}</span><Button disabled>View import history</Button></>}/>
    {caseError && <div className="import-error" role="alert">Could not load cases: {caseError}</div>}
    <div className="import-progress" aria-label="Import progress">{["Select source", "Choose file", "Validate", "Review & import"].map((label, index) => <div className={index + 1 <= completedSteps ? "active" : ""} key={label}><i>{index + 1 < completedSteps ? "✓" : index + 1}</i><span>{label}</span>{index < 3 && <em/>}</div>)}</div>
    <div className="import-grid"><section className="import-main"><EvidenceSourcePicker value={configuration.source} disabled={busy} onChange={updateSource}/><EvidenceFileIntake inputRef={inputRef} file={workflow.file} busy={busy} dragActive={dragActive} onBrowse={chooseFile} onFile={selectFile} onRemove={() => dispatch({ type: "REMOVE_FILE" })} onDragActive={setDragActive}/><ImportConfigurationPanel configuration={configuration} disabled={busy} onChange={updateConfiguration} cases={caseOptions} mock={importDataSource.capability === "mock"}/></section>
      <aside className="import-side"><WorkflowStatus state={workflow.state} error={workflow.error} errorRef={errorRef} capability={importDataSource.capability}/><ValidationSummary result={workflow.validation} capability={importDataSource.capability}/><ImportActions state={workflow.state} hasFile={workflow.file?.validation.status === "valid" && Boolean(configuration.caseId)} hasValidation={Boolean(workflow.validation?.acceptedRecords)} retryable={workflow.state === "cancelled" || Boolean(workflow.error?.retryable)} onValidate={validate} onImport={commit} onCancel={cancel} onRetry={retry} capability={importDataSource.capability} partial={Boolean(workflow.validation?.rejectedRecords)}/></aside></div></>;
}
