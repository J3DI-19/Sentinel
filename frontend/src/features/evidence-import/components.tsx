import type { ChangeEvent, DragEvent, KeyboardEvent, RefObject } from "react";
import { Button, Panel, StatusBadge } from "../../components/ui/core";
import { ACCEPTED_EVIDENCE_EXTENSIONS, formatFileSize } from "./fileValidation";
import type { EvidenceSource, ImportConfiguration, ImportDataError, ImportValidationResult, ImportWorkflowState, SelectedEvidenceFile } from "./types";

export const EVIDENCE_SOURCES: { id: EvidenceSource; label: string; abbreviation: string; description: string }[] = [
  { id: "casas", label: "CASAS", abbreviation: "CA", description: "Primary smart-home telemetry source" },
  { id: "ton_iot_telemetry", label: "TON_IoT Telemetry", abbreviation: "TI", description: "Primary smart-device telemetry source" },
  { id: "simulation", label: "Simulation", abbreviation: "SI", description: "Controlled Traceveil test scenarios" },
  { id: "generic", label: "Generic Upload", abbreviation: "UP", description: "CSV or JSON evidence; CICIoT is secondary compatibility" },
];

export function EvidenceSourcePicker({ value, disabled, onChange }: { value: EvidenceSource; disabled: boolean; onChange: (source: EvidenceSource) => void }) {
  return <Panel title="1. Evidence source"><div className="source-grid">{EVIDENCE_SOURCES.map(source => <button type="button" disabled={disabled} aria-pressed={value === source.id} className={value === source.id ? "selected" : ""} onClick={() => onChange(source.id)} key={source.id}><i>{source.abbreviation}</i><div><b>{source.label}</b><span>{source.description}</span></div><em aria-hidden="true">✓</em></button>)}</div></Panel>;
}

export function EvidenceFileIntake({ inputRef, file, busy, dragActive, onBrowse, onFile, onRemove, onDragActive }: { inputRef: RefObject<HTMLInputElement | null>; file: SelectedEvidenceFile | null; busy: boolean; dragActive: boolean; onBrowse: () => void; onFile: (file: File) => void; onRemove: () => void; onDragActive: (active: boolean) => void }) {
  const choose = () => { if (!busy) onBrowse(); };
  const onInput = (event: ChangeEvent<HTMLInputElement>) => { const selected = event.target.files?.[0]; if (selected) onFile(selected); event.target.value = ""; };
  const onDrop = (event: DragEvent<HTMLDivElement>) => { event.preventDefault(); onDragActive(false); const files = [...event.dataTransfer.files]; if (files.length === 1) onFile(files[0]); };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); } };
  return <Panel title="2. Upload evidence">
    <input ref={inputRef} className="visually-hidden" type="file" accept={ACCEPTED_EVIDENCE_EXTENSIONS} onChange={onInput} aria-label="Choose evidence file" />
    <div className={`dropzone ${dragActive ? "drag-active" : ""} ${busy ? "disabled" : ""}`} role="button" tabIndex={busy ? -1 : 0} aria-disabled={busy} aria-label="Drop a CSV or JSON evidence file, or press Enter to browse" onClick={choose} onKeyDown={onKeyDown} onDragEnter={event => { event.preventDefault(); if (!busy) onDragActive(true); }} onDragOver={event => event.preventDefault()} onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) onDragActive(false); }} onDrop={onDrop}>
      <div className="upload-icon" aria-hidden="true">⇧</div><h3>Drop one evidence file here</h3><p>or <span className="browse-label">browse this device</span></p><span>CSV or JSON · Maximum 50 MiB · Server validation remains authoritative</span>
    </div>
    {file && <div className={`uploaded-file ${file.validation.status === "invalid" ? "file-invalid" : ""}`}><i aria-hidden="true">▤</i><div><b>{file.name}</b><span>{formatFileSize(file.sizeBytes)} · {file.mediaType}</span></div><StatusBadge status={file.validation.status === "valid" ? "Ready" : "Invalid"}/><button type="button" onClick={onRemove} disabled={busy} aria-label={`Remove ${file.name}`}>×</button></div>}
  </Panel>;
}

export function ImportConfigurationPanel({ configuration, disabled, onChange, cases = [], mock = true }: { configuration: ImportConfiguration; disabled: boolean; onChange: (next: ImportConfiguration) => void; cases?: { id: number; name: string }[]; mock?: boolean }) {
  const update = <K extends keyof ImportConfiguration>(key: K, value: ImportConfiguration[K]) => onChange({ ...configuration, [key]: value });
  return <Panel title="3. Import configuration"><div className="form-grid">
    <label><span>Case destination</span><select disabled={disabled} value={configuration.caseId} onChange={event => update("caseId", event.target.value)}>{mock ? <option value="demo-case">Demo case · Mock adapter only</option> : <><option value="">{cases.length ? "Choose a persisted case" : "No cases yet — create one in Cases"}</option>{cases.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</>}</select></label>
    <label><span>Timezone</span><select disabled={disabled} value={configuration.timezone} onChange={event => update("timezone", event.target.value)}><option value="UTC">UTC · Stored forensic time</option><option value="Asia/Kolkata">Asia/Kolkata · Display only</option></select></label>
    <label><span>Timestamp field</span><select disabled={disabled} value={configuration.timestampField} onChange={event => update("timestampField", event.target.value)}><option value="auto">Auto-detect during validation</option></select></label>
    <label><span>Duplicate policy</span><select disabled={disabled} value={configuration.duplicatePolicy} onChange={event => update("duplicatePolicy", event.target.value as ImportConfiguration["duplicatePolicy"])}><option value="skip_exact_hashes">Skip exact content hashes</option></select></label>
    <label className="full"><span>Evidence label</span><input disabled={disabled} value={configuration.label ?? ""} placeholder="Optional investigator label" onChange={event => update("label", event.target.value)} /></label>
  </div></Panel>;
}

export function WorkflowStatus({ state, error, errorRef, capability = "mock" }: { state: ImportWorkflowState; error: ImportDataError | null; errorRef: RefObject<HTMLDivElement | null>; capability?: "mock" | "backend" }) {
  const mock = capability === "mock";
  const copy: Record<ImportWorkflowState, string> = { idle: "Choose a CSV or JSON file to begin.", selecting: "Choose one evidence file from this device.", ready: `File passed local checks and is ready for ${mock ? "mock" : "server"} validation.`, uploading: mock ? "Preparing evidence for the mock adapter…" : "Uploading evidence for persisted validation…", validating: `${mock ? "Mock adapter" : "Backend worker"} is validating the evidence…`, reviewing: "Review the validation result before importing.", importing: mock ? "Mock adapter is simulating the import…" : "The backend is normalizing and analyzing accepted records…", success: mock ? "Mock import completed. No backend data was written." : "Evidence and analysis were persisted successfully.", "partial-success": `${mock ? "Mock" : "Persisted"} import completed with rejected or duplicate records.`, cancelled: "Processing was cancelled. The selected file is still available.", failed: error?.message ?? "The workflow failed." };
  return <Panel title="Workflow status"><div className={`workflow-state state-${state}`} aria-live="polite" aria-atomic="true"><StatusBadge status={state.replace("-", " ")}/><p>{copy[state]}</p>{["uploading", "validating", "importing"].includes(state) && <div className="indeterminate-progress" role="progressbar" aria-label={copy[state]}><i /></div>}</div>{error && <div className="import-error" ref={errorRef} tabIndex={-1} role="alert"><b>{error.retryable ? "Temporary problem" : "Action required"}</b><p>{error.message}</p><code>{error.code}</code></div>}</Panel>;
}

export function ValidationSummary({ result, capability = "mock" }: { result: ImportValidationResult | null; capability?: "mock" | "backend" }) {
  const copyReference = () => { if (result?.rejectionLogReference) void navigator.clipboard?.writeText(result.rejectionLogReference); };
  return <Panel title="Validation summary">{!result ? <div className="import-empty"><span aria-hidden="true">◇</span><b>No validation result</b><p>Results appear only after a selected file is processed by the {capability === "mock" ? "mock adapter" : "connected API"}.</p></div> : <><div className="validation-score"><div><b>{result.acceptedRecords}</b><span>Accepted</span></div><p>{result.detectedSchema}<br/>Detected source: {result.detectedSource.replaceAll("_", " ")}</p></div><dl className="validation-list"><div><dt>Source records</dt><dd>{result.totalRecords}</dd></div><div><dt>Accepted</dt><dd className="success">{result.acceptedRecords}</dd></div><div><dt>Rejected</dt><dd className={result.rejectedRecords ? "danger" : ""}>{result.rejectedRecords}</dd></div><div><dt>Duplicates</dt><dd>{result.duplicateRecords}</dd></div></dl>{result.warnings.map(warning => <p className="import-warning" key={warning}>{warning}</p>)}{result.problems.length > 0 && <div className="rejections" aria-label="Validation problems">{result.problems.map(problem => <div key={`${problem.code}-${problem.row ?? "file"}`}><i>!</i><div><b>{problem.code}{problem.row ? ` · Row ${problem.row}` : ""}</b><span>{problem.message}</span>{problem.correction && <span>{problem.correction}</span>}</div></div>)}</div>}{result.rejectionLogReference && <p className="import-warning"><b>Rejection reference:</b> <code>{result.rejectionLogReference}</code> <Button onClick={copyReference}>Copy reference</Button></p>}</>}</Panel>;
}

export function ImportActions({ state, hasFile, hasValidation, retryable, onValidate, onImport, onCancel, onRetry, capability = "mock", partial = false }: { state: ImportWorkflowState; hasFile: boolean; hasValidation: boolean; retryable: boolean; onValidate: () => void; onImport: () => void; onCancel: () => void; onRetry: () => void; capability?: "mock" | "backend"; partial?: boolean }) {
  const busy = ["uploading", "validating", "importing"].includes(state);
  const mock = capability === "mock"; const adapter = mock ? "mock adapter" : "backend";
  return <div className="import-result"><div><span>{mock ? "Mock adapter" : "Connected API"}</span><b>{mock ? "Frontend-only workflow" : "Persisted batch workflow"}</b><p>{mock ? "Processing is deterministic demonstration behavior. Nothing is uploaded, persisted, or forensically analyzed." : partial ? "Approval persists accepted records; rejected rows remain excluded and are not canonical evidence." : "Validation is non-destructive. Commit persists accepted records and deterministic analysis."}</p></div>{state === "reviewing" ? <Button variant="primary" onClick={onImport} disabled={!hasValidation}>{partial ? "Approve partial import" : `Import with ${adapter}`} →</Button> : (state === "failed" || state === "cancelled") && retryable ? <Button variant="primary" onClick={onRetry} disabled={!hasFile}>Retry processing</Button> : <Button variant="primary" onClick={onValidate} disabled={!hasFile || busy || state === "success" || state === "partial-success"}>Validate with {adapter} →</Button>}{busy && <Button variant="danger" onClick={onCancel}>Cancel processing</Button>}<small>{mock ? "Mock adapter · No backend connection or persistence" : "Connected API · Original evidence is content-addressed and immutable"}</small></div>;
}
