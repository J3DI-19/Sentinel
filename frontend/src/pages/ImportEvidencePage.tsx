import { useEffect, useReducer, useRef, useState } from "react";
import { normalizeApiError } from "../api/client";
import { batchApi, type ApiCase } from "../api/batch";
import { Button, EmptyState, PageHeader } from "../components/ui/core";
import { EvidenceFileIntake, EvidenceSourcePicker, ImportActions, ImportConfigurationPanel, SourceFormatGuide, ValidationSummary, WorkflowStatus } from "../features/evidence-import/components";
import { inspectEvidenceFile } from "../features/evidence-import/fileValidation";
import { importDataSource } from "../features/evidence-import/importDataSource";
import type { EvidenceSource, ImportConfiguration, ImportDataSource } from "../features/evidence-import/types";
import { importWorkflowReducer, initialImportWorkflow } from "../features/evidence-import/workflow";
import "../import-workflow.css";

const initialConfiguration = (capability: ImportDataSource["capability"]): ImportConfiguration => ({ caseId: capability === "mock" ? "demo-case" : "", source: "ton_iot_fridge_telemetry", timezone: "UTC", timestampField: "auto", duplicatePolicy: "skip_exact_hashes", label: "" });

export function ImportEvidencePage({ search = "", navigate = () => {}, dataSource = importDataSource }: { search?: string; navigate?: (path: string) => void; dataSource?: ImportDataSource }) {
  const [workflow, dispatch] = useReducer(importWorkflowReducer, initialImportWorkflow);
  const [configuration, setConfiguration] = useState(() => initialConfiguration(dataSource.capability));
  const [dragActive, setDragActive] = useState(false);
  const [caseOptions, setCaseOptions] = useState<ApiCase[]>([]);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [caseSelectionMessage, setCaseSelectionMessage] = useState<string | null>(null);
  const [caseLoading, setCaseLoading] = useState(dataSource.capability === "backend");
  const [partialApproved, setPartialApproved] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const operationRef = useRef<AbortController | null>(null);
  const operationActiveRef = useRef(false);
  const busy = ["uploading", "validating", "importing"].includes(workflow.state);

  useEffect(() => { if (workflow.state === "failed") errorRef.current?.focus(); }, [workflow.state]);
  useEffect(() => () => operationRef.current?.abort(), []);
  useEffect(() => {
    if (dataSource.capability === "mock") { setCaseLoading(false); return; }
    const controller = new AbortController();
    setCaseLoading(true); setCaseError(null); setCaseSelectionMessage(null);
    void batchApi.listCases(controller.signal).then(result => {
      const items = Array.isArray(result.items) ? result.items : [];
      setCaseOptions(items);
      const requested = new URLSearchParams(search).get("case");
      if (requested !== null) {
        const requestedId = Number(requested);
        const match = Number.isInteger(requestedId) && requestedId > 0 ? items.find(item => item.id === requestedId) : undefined;
        setConfiguration(current => ({ ...current, caseId: match ? String(match.id) : "" }));
        if (!match) setCaseSelectionMessage(Number.isInteger(requestedId) && requestedId > 0 ? "The requested case is no longer available. Choose another persisted case before importing." : "The requested case ID is invalid. Choose a persisted case before importing.");
      } else {
        setConfiguration(current => ({ ...current, caseId: items[0] ? String(items[0].id) : "" }));
      }
    }).catch(error => { if (!controller.signal.aborted) { setCaseOptions([]); setConfiguration(current => ({ ...current, caseId: "" })); setCaseError(normalizeApiError(error).message); } }).finally(() => { if (!controller.signal.aborted) setCaseLoading(false); });
    return () => controller.abort();
  }, [dataSource.capability, search]);

  const chooseFile = () => { dispatch({ type: "SELECTING" }); inputRef.current?.click(); };
  const selectFile = (file: File) => {
    setPartialApproved(false);
    const selected = inspectEvidenceFile(file);
    if (selected.validation.status === "invalid") dispatch({ type: "FILE_REJECTED", file: selected, error: { code: selected.validation.code, message: selected.validation.message, retryable: false } });
    else dispatch({ type: "FILE_SELECTED", file: selected });
  };
  const updateConfiguration = (next: ImportConfiguration) => { setConfiguration(next); setPartialApproved(false); if (caseOptions.some(item => String(item.id) === next.caseId)) setCaseSelectionMessage(null); dispatch({ type: "CONFIGURATION_CHANGED" }); };
  const updateSource = (source: EvidenceSource) => updateConfiguration({ ...configuration, source });

  const validate = async () => {
    if (!workflow.file || busy || operationActiveRef.current || (dataSource.capability === "backend" && !caseOptions.some(item => String(item.id) === configuration.caseId))) return;
    operationActiveRef.current = true;
    const controller = new AbortController(); operationRef.current = controller;
    dispatch({ type: "UPLOAD_STARTED" }); dispatch({ type: "VALIDATION_STARTED" });
    try { const result = await dataSource.validate(workflow.file, configuration, controller.signal); dispatch({ type: "VALIDATION_SUCCEEDED", result }); }
    catch (error) { if (!controller.signal.aborted) dispatch({ type: "FAILED", error: normalizeApiError(error) }); }
    finally { operationActiveRef.current = false; if (operationRef.current === controller) operationRef.current = null; }
  };
  const commit = async () => {
    if (!workflow.validation || busy || operationActiveRef.current || (workflow.validation.rejectedRecords > 0 && !partialApproved)) return;
    operationActiveRef.current = true;
    const controller = new AbortController(); operationRef.current = controller; dispatch({ type: "IMPORT_STARTED" });
    try { const status = await dataSource.commit(workflow.validation.validationId, configuration, controller.signal); dispatch({ type: "IMPORT_SUCCEEDED", importId: status.importId, partial: workflow.validation.rejectedRecords > 0 || workflow.validation.duplicateRecords > 0 }); }
    catch (error) { if (!controller.signal.aborted) dispatch({ type: "FAILED", error: normalizeApiError(error) }); }
    finally { operationActiveRef.current = false; if (operationRef.current === controller) operationRef.current = null; }
  };
  const cancel = () => { operationRef.current?.abort(); operationRef.current = null; dispatch({ type: "CANCELLED" }); void dataSource.cancel(workflow.importId, new AbortController().signal); };
  const retry = () => { dispatch({ type: "RETRY" }); void validate(); };
  const completedSteps = workflow.state === "idle" || workflow.state === "selecting" ? 1 : workflow.state === "ready" || workflow.state === "uploading" || workflow.state === "validating" || workflow.state === "failed" || workflow.state === "cancelled" ? 2 : workflow.state === "reviewing" || workflow.state === "importing" ? 3 : 4;

  const validCase = dataSource.capability === "mock" || caseOptions.some(item => String(item.id) === configuration.caseId);
  const capabilityLabel = dataSource.capability === "mock" ? "Mock adapter" : "Connected API";
  return <><PageHeader eyebrow={`Evidence intake · ${capabilityLabel}`} title="Import evidence" description={dataSource.capability === "mock" ? "Prepare CSV or JSON evidence without backend persistence." : "Validate evidence first, then explicitly commit accepted records to the selected case."} actions={<span className="capability-chip">{capabilityLabel}</span>}/>
    {caseError && <div className="import-error" role="alert"><b>Cases could not be loaded</b><p>{caseError}</p><Button onClick={() => navigate("/cases")}>Open Cases</Button></div>}
    {!caseLoading && !caseError && dataSource.capability === "backend" && caseOptions.length === 0 && <EmptyState className="empty-state--standalone" title="No persisted cases" description="Create a case before importing evidence." action={<Button variant="primary" onClick={() => navigate("/cases")}>Open Cases</Button>}/>}
    {caseSelectionMessage && <div className="import-error" role="alert"><b>Case selection required</b><p>{caseSelectionMessage}</p><Button onClick={() => navigate("/cases")}>Open Cases</Button></div>}
    <div className="import-progress" aria-label="Import progress">{["Select source", "Choose file", "Validate", "Review & import"].map((label, index) => <div className={index + 1 <= completedSteps ? "active" : ""} key={label}><i>{index + 1 < completedSteps ? "✓" : index + 1}</i><span>{label}</span>{index < 3 && <em/>}</div>)}</div>
    <div className="import-grid"><section className="import-main"><EvidenceSourcePicker value={configuration.source} disabled={busy} onChange={updateSource}/><SourceFormatGuide source={configuration.source}/><EvidenceFileIntake inputRef={inputRef} file={workflow.file} busy={busy} dragActive={dragActive} onBrowse={chooseFile} onFile={selectFile} onRemove={() => { setPartialApproved(false); dispatch({ type: "REMOVE_FILE" }); }} onDragActive={setDragActive}/><ImportConfigurationPanel configuration={configuration} disabled={busy || caseLoading || Boolean(caseError) || (dataSource.capability === "backend" && !caseOptions.length)} onChange={updateConfiguration} cases={caseOptions} mock={dataSource.capability === "mock"}/></section>
      <aside className="import-side"><WorkflowStatus state={workflow.state} error={workflow.error} errorRef={errorRef} capability={dataSource.capability}/><ValidationSummary result={workflow.validation} capability={dataSource.capability}/><ImportActions state={workflow.state} hasFile={workflow.file?.validation.status === "valid" && validCase} hasValidation={Boolean(workflow.validation?.acceptedRecords)} retryable={workflow.state === "cancelled" || Boolean(workflow.error?.retryable)} onValidate={validate} onImport={commit} onCancel={cancel} onRetry={retry} onOpenResults={() => navigate(`/cases/${configuration.caseId}/overview`)} capability={dataSource.capability} partial={Boolean(workflow.validation?.rejectedRecords)} acceptedRecords={workflow.validation?.acceptedRecords} rejectedRecords={workflow.validation?.rejectedRecords} partialApproved={partialApproved} onPartialApproved={setPartialApproved}/></aside></div></>;
}
