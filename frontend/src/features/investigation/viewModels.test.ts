import { describe, expect, it } from "vitest";
import { mapInvestigationRecord, mapInvestigationRecords } from "./viewModels";

describe("investigation DTO mapping", () => {
  it("preserves identifiers, UTC values, provenance, traces, and risk factors", () => {
    const payload = { event_id: "evt-1", observed_at: "2026-08-15T01:02:03Z", event_type: "motion", entity_id: "sensor-7", provenance: { row: 4 }, rule_trace: ["R-1"], risk_factors: { burst: 12 }, score: 73 };
    const result = mapInvestigationRecord("events", payload);
    expect(result).toMatchObject({ id: "evt-1", timestampUtc: payload.observed_at, category: "motion", entityId: "sensor-7", risk: 73, provenance: payload.provenance, ruleTrace: payload.rule_trace, riskFactors: payload.risk_factors });
    expect(result.source).toEqual(payload);
  });
  it("retains null-heavy and unknown-enum records without inventing conclusions", () => {
    expect(mapInvestigationRecord("alerts", { alert_id: "a-1", severity: "future_severity", occurred_at: null, risk: null })).toMatchObject({ id: "a-1", severity: "future_severity", timestampUtc: null, risk: null });
  });
  it("keeps partial collections and gives malformed records stable fallback IDs", () => {
    expect(mapInvestigationRecords("findings", [{ finding_id: "f-1" }, null]).map(item => item.id)).toEqual(["f-1", "findings-1"]);
  });
});
