export type InvestigationRecordKind = "evidence" | "events" | "findings" | "alerts" | "incidents" | "timeline" | "aggregates" | "audit" | "graph";

export interface InvestigationRecordViewModel {
  id: string; kind: InvestigationRecordKind; title: string; timestampUtc: string | null;
  origin: string | null; category: string | null; entityId: string | null;
  severity: string | null; risk: number | null; provenance: unknown | null;
  ruleTrace: unknown | null; riskFactors: unknown | null; source: Readonly<Record<string, unknown>>;
}

const record = (value: unknown): Record<string, unknown> => value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const string = (value: unknown): string | null => typeof value === "string" && value.length > 0 ? value : null;
const number = (value: unknown): number | null => typeof value === "number" && Number.isFinite(value) ? value : null;
function first(source: Record<string, unknown>, keys: string[]): unknown { for (const key of keys) if (key in source) return source[key]; return null; }

/** Maps a contract record once and retains the untouched payload for forensic inspection. */
export function mapInvestigationRecord(kind: InvestigationRecordKind, value: unknown, index = 0): InvestigationRecordViewModel {
  const source = record(value);
  const id = string(first(source, ["evidence_id", "event_id", "finding_id", "alert_id", "incident_id", "entry_id", "timeline_id", "audit_id", "node_id", "edge_id", "item_id", "id"])) ?? `${kind}-${index}`;
  const category = string(first(source, ["event_type", "kind", "type", "action", "source_type", "source"]));
  return { id, kind, title: string(first(source, ["title", "original_name", "filename", "message", "label", "name"])) ?? category ?? id,
    timestampUtc: string(first(source, ["observed_at", "timestamp", "occurred_at", "created_at", "started_at", "received_at", "ingested_at"])),
    origin: string(first(source, ["origin", "source_type", "source"])), category,
    entityId: string(first(source, ["entity_id", "entity", "sensor_id", "subject_id"])), severity: string(source.severity),
    risk: number(source.risk_score ?? source.score ?? record(source.risk).score), provenance: source.provenance ?? null,
    ruleTrace: first(source, ["condition_trace", "rule_trace", "rule_traces", "rule_id"]), riskFactors: source.risk_factors ?? source.factors ?? record(source.risk).factors ?? null,
    source: Object.freeze({ ...source }) };
}

export function mapInvestigationRecords(kind: InvestigationRecordKind, values: unknown[]): InvestigationRecordViewModel[] { return values.map((value, index) => mapInvestigationRecord(kind, value, index)); }
