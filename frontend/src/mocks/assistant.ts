import type { Severity, TimelineEntry } from "../types/domain";

export type VisualizationComponentType =
  | "metric-card"
  | "bar-chart"
  | "line-chart"
  | "area-chart"
  | "pie-chart"
  | "evidence-table"
  | "investigation-timeline"
  | "device-graph"
  | "finding-panel"
  | "risk-breakdown"
  | "text-summary";

export interface VisualizationComponentSpec {
  id: string;
  type: VisualizationComponentType | string;
  title: string;
  dataRef: string;
  span?: 1 | 2 | 3;
  height?: "compact" | "standard" | "tall";
}

export interface VisualizationSpec {
  id: string;
  name: string;
  description: string;
  evidenceRefs: string[];
  components: VisualizationComponentSpec[];
}

export interface AssistantPrompt {
  id: string;
  label: string;
  request: string;
  response: string;
  narration: string;
  references: string[];
  specId: string;
}

export interface AssistantMessageData {
  id: string;
  role: "assistant" | "user";
  text: string;
  kind?: "verified" | "narration";
  references?: string[];
}

export const assistantContext = [
  { id: "FND-1042", label: "Finding F-019", kind: "Finding" },
  { id: "ALT-8831", label: "Alert ALT-012", kind: "Alert" },
  { id: "EVD-2026-8F21", label: "Evidence EVT-00421", kind: "Evidence" },
  { id: "dev-camera-01", label: "Device CAM-01", kind: "Device" },
];

export const initialAssistantMessages: AssistantMessageData[] = [
  { id: "welcome", role: "assistant", kind: "narration", text: "I’m ready to help examine this case. I’ll keep verified evidence separate from explanatory narration and cite every record used." },
  { id: "request-1", role: "user", text: "Show me the device activity surrounding this alert." },
  { id: "answer-1", role: "assistant", kind: "verified", text: "CAM-01 showed a burst of failed authentication attempts followed by a successful login from an unseen peer. Related activity was also observed on the Northbridge gateway within the configured 120-second correlation window.", references: ["EVT-421", "EVT-428", "ALT-012", "F-019"] },
];

export const assistantPrompts: AssistantPrompt[] = [
  { id: "global-date", label: "Summarize 17 July", request: "Summarize what happened on 17 July.", response: "Verified retrieval found activity across three investigations on 17 July: 31 alerts, four critical findings, and a concentrated authentication spike affecting the Northbridge camera environment. The related records span live capture and preserved batch evidence.", narration: "The strongest pattern is the Northbridge credential-attack sequence, while the thermostat and gateway investigations contribute lower-confidence supporting activity. Review the cited cases and preserved records before treating that relationship as a conclusion.", references: ["TV-2026-024", "TV-2026-023", "TV-2026-021", "FND-1042", "ALT-8831", "EVD-2026-8F21"], specId: "global-july17" },
  { id: "global-camera", label: "Suspicious camera activity", request: "Show suspicious camera activity.", response: "Verified retrieval found 48 authentication events, fourteen privileged failures, one successful external session, and subsequent RTSP command activity involving CAM-01. Three preserved evidence records and one critical finding support the sequence.", narration: "The activity is consistent with attempted credential compromise followed by camera access, but intent remains an investigator judgment rather than a deterministic fact.", references: ["TV-2026-024", "CAM-01", "EVD-2026-8F19", "EVD-2026-8F21", "ALT-8831", "FND-1042"], specId: "global-camera" },
  { id: "global-risk", label: "Highest-risk unresolved findings", request: "What are the highest-risk unresolved findings?", response: "Three unresolved mock findings rank highest: FND-1042 at 96 risk, FND-1041 at 83, and FND-1038 at 61. Their supporting evidence remains linked to the Northbridge camera, gateway, and door-sensor activity.", narration: "FND-1042 should be reviewed first because it combines the highest deterministic score, critical asset exposure, and the strongest cross-source temporal correlation.", references: ["FND-1042", "FND-1041", "FND-1038", "TV-2026-024", "EVD-2026-8F21"], specId: "global-risk" },
  { id: "explain-finding", label: "Explain this finding", request: "Explain why this finding is critical.", response: "Verified evidence links fourteen privileged authentication failures, one successful session from the same external peer, and camera-control traffic 74 seconds later.", narration: "The sequence is consistent with a credential attack progressing into device access; that interpretation should still be reviewed by an investigator.", references: ["FND-1042", "EVT-421", "EVT-428"], specId: "incident-context" },
  { id: "leading-events", label: "Show events leading to this alert", request: "Show the events leading to this alert.", response: "The alert threshold was crossed after the fourteenth failed administrator login. Gateway connection attempts and historical reconnaissance records precede it inside the selected window.", narration: "The canvas is ordered by preserved timestamp so the lead-in can be reviewed without AI-generated chronology.", references: ["EVT-414", "EVT-421", "ALT-012"], specId: "incident-context" },
  { id: "compare-devices", label: "Compare involved devices", request: "Compare the involved devices.", response: "CAM-01 carries the highest case risk and the greatest authentication activity. GW-01 has broader network activity and provides the strongest cross-device link to the external peer.", narration: "This comparison uses the same deterministic device aggregates available in case analytics.", references: ["EVT-421", "EVT-428", "DEV-CAM-01", "DEV-GW-01"], specId: "device-comparison" },
  { id: "chronology", label: "Visualize the incident chronology", request: "Visualize the incident chronology.", response: "The verified sequence begins with gateway reconnaissance, continues through repeated camera authentication failures, and concludes with a correlated critical finding after control traffic was observed.", narration: "The timeline reflects preserved event timestamps; the assistant only selected and arranged the view.", references: ["EVT-398", "EVT-400", "EVT-421", "FND-1042"], specId: "incident-chronology" },
  { id: "correlation", label: "Explain this correlation path", request: "Explain this correlation path.", response: "The external peer connects through GW-01, appears in CAM-01 authentication evidence, and is linked to the later RTSP command by actor IP and temporal proximity.", narration: "The path is an explanation of deterministic links, not a newly inferred relationship.", references: ["EVT-398", "EVT-421", "EVT-428", "FND-1042"], specId: "correlation-path" },
  { id: "summary", label: "Summarize selected evidence", request: "Summarize the selected evidence.", response: "Four selected records support a credential-attack sequence affecting CAM-01 through GW-01. One critical finding remains open for investigator review.", narration: "Open the evidence references below to validate the source records before using this summary in a report.", references: ["EVT-398", "EVT-421", "ALT-012", "FND-1042"], specId: "evidence-summary" },
];

export const visualizationSpecs: Record<string, VisualizationSpec> = {
  "global-overview": { id: "global-overview", name: "Traceveil investigation overview", description: "Cross-workspace verified context ready for natural-language exploration", evidenceRefs: ["TV-2026-024", "TV-2026-023", "FND-1042", "ALT-8831"], components: [
    { id: "cases", type: "metric-card", title: "Open investigations", dataRef: "global-case-count", span: 1, height: "compact" },
    { id: "findings", type: "metric-card", title: "Unresolved findings", dataRef: "global-finding-count", span: 1, height: "compact" },
    { id: "alerts", type: "metric-card", title: "Recent alerts", dataRef: "global-alert-count", span: 1, height: "compact" },
    { id: "activity", type: "area-chart", title: "Cross-case activity", dataRef: "global-event-activity", span: 2 },
    { id: "summary", type: "text-summary", title: "Retrieval-ready context", dataRef: "global-overview-summary", span: 1 },
    { id: "finding", type: "finding-panel", title: "Highest-risk unresolved finding", dataRef: "primary-finding", span: 3 },
  ]},
  "global-july17": { id: "global-july17", name: "17 July investigation summary", description: "Mock retrieval across cases, alerts, findings, and preserved events", evidenceRefs: ["TV-2026-024", "TV-2026-023", "TV-2026-021", "FND-1042", "ALT-8831", "EVD-2026-8F21"], components: [
    { id: "cases", type: "metric-card", title: "Related cases", dataRef: "july17-case-count", span: 1, height: "compact" },
    { id: "alerts", type: "metric-card", title: "Alerts retrieved", dataRef: "july17-alert-count", span: 1, height: "compact" },
    { id: "critical", type: "metric-card", title: "Critical findings", dataRef: "july17-critical-count", span: 1, height: "compact" },
    { id: "activity", type: "area-chart", title: "Event activity · 17 July", dataRef: "july17-event-activity", span: 2 },
    { id: "related", type: "text-summary", title: "Related investigations", dataRef: "july17-related-cases", span: 1 },
    { id: "timeline", type: "investigation-timeline", title: "Cross-case timeline", dataRef: "global-cross-case-timeline", span: 3, height: "tall" },
  ]},
  "global-camera": { id: "global-camera", name: "Suspicious camera activity", description: "Retrieved authentication, connection, command, and finding context", evidenceRefs: ["TV-2026-024", "CAM-01", "EVD-2026-8F19", "EVD-2026-8F21", "ALT-8831", "FND-1042"], components: [
    { id: "camera-count", type: "metric-card", title: "Affected cameras", dataRef: "camera-affected-count", span: 1, height: "compact" },
    { id: "camera-risk", type: "metric-card", title: "Highest camera risk", dataRef: "incident-risk", span: 1, height: "compact" },
    { id: "camera-events", type: "metric-card", title: "Retrieved events", dataRef: "camera-event-count", span: 1, height: "compact" },
    { id: "activity", type: "area-chart", title: "Camera event activity", dataRef: "incident-event-activity", span: 2 },
    { id: "finding", type: "finding-panel", title: "Related critical finding", dataRef: "primary-finding", span: 1 },
    { id: "evidence", type: "evidence-table", title: "Supporting camera evidence", dataRef: "chronology-evidence", span: 3 },
  ]},
  "global-risk": { id: "global-risk", name: "Highest-risk unresolved findings", description: "Deterministic risk ranking across current mock investigations", evidenceRefs: ["FND-1042", "FND-1041", "FND-1038", "TV-2026-024"], components: [
    { id: "count", type: "metric-card", title: "Unresolved findings", dataRef: "global-finding-count", span: 1, height: "compact" },
    { id: "critical", type: "metric-card", title: "Critical unresolved", dataRef: "global-critical-unresolved", span: 1, height: "compact" },
    { id: "top", type: "metric-card", title: "Highest risk", dataRef: "incident-risk", span: 1, height: "compact" },
    { id: "ranking", type: "bar-chart", title: "Finding risk comparison", dataRef: "global-finding-risk", span: 2 },
    { id: "finding", type: "finding-panel", title: "Priority finding", dataRef: "primary-finding", span: 1 },
    { id: "summary", type: "text-summary", title: "Retrieved investigation context", dataRef: "global-risk-summary", span: 3 },
  ]},
  "incident-context": { id: "incident-context", name: "Activity surrounding alert", description: "Verified activity within the selected correlation window", evidenceRefs: ["EVT-414", "EVT-421", "EVT-428", "ALT-012", "FND-1042"], components: [
    { id: "risk", type: "metric-card", title: "Incident risk", dataRef: "incident-risk", span: 1, height: "compact" },
    { id: "summary", type: "text-summary", title: "Verified incident context", dataRef: "incident-summary", span: 2, height: "compact" },
    { id: "activity", type: "area-chart", title: "Event activity", dataRef: "incident-event-activity", span: 2 },
    { id: "timeline", type: "investigation-timeline", title: "Investigation timeline", dataRef: "incident-timeline", span: 1, height: "tall" },
    { id: "graph", type: "device-graph", title: "Related device graph", dataRef: "correlation-graph", span: 3 },
  ]},
  "device-comparison": { id: "device-comparison", name: "Involved device comparison", description: "Side-by-side deterministic device aggregates", evidenceRefs: ["EVT-421", "EVT-428", "DEV-CAM-01", "DEV-GW-01"], components: [
    { id: "device-activity", type: "bar-chart", title: "Device activity comparison", dataRef: "device-comparison-activity", span: 2 },
    { id: "event-types", type: "pie-chart", title: "Event type distribution", dataRef: "device-event-types", span: 1 },
    { id: "device-risk", type: "bar-chart", title: "Device risk comparison", dataRef: "device-risk", span: 1 },
    { id: "evidence", type: "evidence-table", title: "Supporting evidence", dataRef: "comparison-evidence", span: 2 },
  ]},
  "incident-chronology": { id: "incident-chronology", name: "Incident chronology", description: "Preserved sequence of events, alerts, and findings", evidenceRefs: ["EVT-398", "EVT-400", "EVT-421", "FND-1042"], components: [
    { id: "span", type: "metric-card", title: "Incident span", dataRef: "incident-span", span: 1, height: "compact" },
    { id: "records", type: "metric-card", title: "Correlated records", dataRef: "correlated-records", span: 1, height: "compact" },
    { id: "alerts", type: "metric-card", title: "Related alerts", dataRef: "related-alert-count", span: 1, height: "compact" },
    { id: "timeline", type: "investigation-timeline", title: "Verified chronology", dataRef: "incident-timeline", span: 2, height: "tall" },
    { id: "finding", type: "finding-panel", title: "Related finding", dataRef: "primary-finding", span: 1, height: "tall" },
    { id: "evidence", type: "evidence-table", title: "Supporting evidence", dataRef: "chronology-evidence", span: 3 },
  ]},
  "correlation-path": { id: "correlation-path", name: "Correlation path", description: "Allow-listed entity links and risk factors", evidenceRefs: ["EVT-398", "EVT-421", "EVT-428", "FND-1042"], components: [
    { id: "graph", type: "device-graph", title: "Device and entity path", dataRef: "correlation-graph", span: 2, height: "tall" },
    { id: "details", type: "text-summary", title: "Correlation details", dataRef: "correlation-summary", span: 1 },
    { id: "linked", type: "evidence-table", title: "Linked events", dataRef: "correlation-evidence", span: 2 },
    { id: "factors", type: "risk-breakdown", title: "Risk factor breakdown", dataRef: "risk-factors", span: 1 },
  ]},
  "evidence-summary": { id: "evidence-summary", name: "Selected evidence summary", description: "Compact review of records currently in context", evidenceRefs: ["EVT-398", "EVT-421", "ALT-012", "FND-1042"], components: [
    { id: "summary", type: "text-summary", title: "Evidence-grounded summary", dataRef: "evidence-summary", span: 2 },
    { id: "risk", type: "risk-breakdown", title: "Risk factors", dataRef: "risk-factors", span: 1 },
    { id: "evidence", type: "evidence-table", title: "Selected evidence", dataRef: "chronology-evidence", span: 3 },
  ]},
};

const incidentTimeline: TimelineEntry[] = [
  { id: "EVT-398", time: "14:31:41", title: "External peer reached camera service", description: "Peer 185.77.12.44 connected through GW-01.", type: "event", severity: "High", evidenceId: "EVT-398" },
  { id: "ALT-012", time: "14:32:08", title: "Authentication threshold crossed", description: "Fourteenth privileged login failure matched AUTH-014.", type: "alert", severity: "Critical", evidenceId: "EVT-421" },
  { id: "EVT-428", time: "14:33:01", title: "Successful session and RTSP command", description: "CAM-01 accepted a session from the same peer.", type: "event", severity: "Critical", evidenceId: "EVT-428" },
  { id: "FND-1042", time: "14:33:22", title: "Correlation finding created", description: "Deterministic pipeline linked the preserved records.", type: "finding", severity: "Critical" },
];

const evidenceRows = [
  { id: "EVT-398", time: "14:31:41", device: "GW-01", event: "connection_attempt", severity: "High" as Severity },
  { id: "EVT-421", time: "14:32:08", device: "CAM-01", event: "authentication_failure", severity: "Critical" as Severity },
  { id: "EVT-428", time: "14:33:01", device: "CAM-01", event: "rtsp_command", severity: "Critical" as Severity },
  { id: "ALT-012", time: "14:32:08", device: "CAM-01", event: "rule_match", severity: "Critical" as Severity },
];

const globalCrossCaseTimeline: TimelineEntry[] = [
  { id: "TV-2026-023-E1", time: "09:18", title: "Thermostat rare-host beacon observed", description: "Batch review linked recurring outbound activity to the thermostat investigation.", type: "event", severity: "High", evidenceId: "EVD-2026-7A12" },
  { id: "TV-2026-021-A1", time: "11:42", title: "Gateway request baseline exceeded", description: "The controlled gateway investigation recorded a sustained request-rate anomaly.", type: "alert", severity: "High", evidenceId: "EVD-2026-7C08" },
  { id: "TV-2026-024-A1", time: "14:32", title: "Camera authentication threshold crossed", description: "Fourteen failed privileged logins triggered the deterministic authentication rule.", type: "alert", severity: "Critical", evidenceId: "EVD-2026-8F21" },
  { id: "TV-2026-024-F1", time: "14:33", title: "Critical camera finding created", description: "Preserved authentication and command records were correlated into FND-1042.", type: "finding", severity: "Critical" },
];

export const visualizationDatasets: Record<string, unknown> = {
  "global-case-count": { value: "03", detail: "Active, monitoring, or in review", tone: "cyan" },
  "global-finding-count": { value: "20", detail: "Across 3 current investigations" },
  "global-alert-count": { value: "31", detail: "4 critical · last 24 hours", tone: "danger" },
  "global-critical-unresolved": { value: "04", detail: "Require investigator review", tone: "danger" },
  "july17-case-count": { value: "03", detail: "Cases with relevant activity", tone: "cyan" },
  "july17-alert-count": { value: "31", detail: "Across retrieved records" },
  "july17-critical-count": { value: "04", detail: "Critical unresolved findings", tone: "danger" },
  "camera-affected-count": { value: "01", detail: "CAM-01 · Entryway camera", tone: "cyan" },
  "camera-event-count": { value: "48", detail: "Authentication and command events" },
  "global-overview-summary": { lead: "Auto retrieval ready", text: "Ask across cases, findings, alerts, evidence, and devices. Traceveil will select relevant mock sources before generating an explanation.", refs: ["TV-2026-024", "FND-1042"] },
  "july17-related-cases": { lead: "Three related investigations", text: "Northbridge Camera Intrusion, Thermostat Beaconing Review, and Gateway Rate Anomaly contain the strongest retrieved activity for 17 July.", refs: ["TV-2026-024", "TV-2026-023", "TV-2026-021"] },
  "global-risk-summary": { lead: "Deterministic ranking", text: "FND-1042, FND-1041, and FND-1038 are ordered by their preserved risk scores. Status and evidence links remain available for investigator review.", refs: ["FND-1042", "FND-1041", "FND-1038"] },
  "global-event-activity": [{ label:"08:00",Events:18,Alerts:1},{label:"10:00",Events:31,Alerts:3},{label:"12:00",Events:46,Alerts:5},{label:"14:00",Events:118,Alerts:14},{label:"16:00",Events:67,Alerts:6},{label:"18:00",Events:29,Alerts:2}],
  "july17-event-activity": [{ label:"08:00",Events:14,Alerts:1},{label:"10:00",Events:28,Alerts:2},{label:"12:00",Events:42,Alerts:4},{label:"14:00",Events:126,Alerts:16},{label:"16:00",Events:59,Alerts:5},{label:"18:00",Events:24,Alerts:3}],
  "global-finding-risk": [{label:"FND-1042",Risk:96},{label:"FND-1041",Risk:83},{label:"FND-1038",Risk:61}],
  "global-cross-case-timeline": globalCrossCaseTimeline,
  "incident-risk": { value: "96", detail: "Critical · deterministic score", tone: "danger" },
  "incident-span": { value: "4m 12s", detail: "14:29:47—14:33:59", tone: "cyan" },
  "correlated-records": { value: "42", detail: "Across 3 evidence sources" },
  "related-alert-count": { value: "03", detail: "1 critical · 2 high", tone: "danger" },
  "incident-summary": { lead: "Verified finding", text: "Fourteen failed administrator logins were followed by a successful session and camera-control traffic from the same external peer within 74 seconds.", refs: ["FND-1042", "ALT-012"] },
  "correlation-summary": { lead: "Deterministic correlation", text: "Actor IP, target identity, and a 120-second temporal window connect gateway traffic to CAM-01 authentication and RTSP activity.", refs: ["RULE-COR-07"] },
  "evidence-summary": { lead: "Selected evidence", text: "Four preserved records support the current context. The finding remains open and requires investigator review before containment or reporting.", refs: ["EVT-398", "EVT-421", "ALT-012", "FND-1042"] },
  "incident-event-activity": [
    { label: "14:29", Events: 8, Alerts: 0 }, { label: "14:30", Events: 14, Alerts: 1 }, { label: "14:31", Events: 28, Alerts: 1 }, { label: "14:32", Events: 61, Alerts: 3 }, { label: "14:33", Events: 37, Alerts: 2 }, { label: "14:34", Events: 16, Alerts: 0 },
  ],
  "device-comparison-activity": [{ label: "CAM-01", Authentication: 48, Network: 31 }, { label: "GW-01", Authentication: 12, Network: 74 }, { label: "SEN-04", Authentication: 0, Network: 19 }],
  "device-event-types": [{ name: "Authentication", value: 44, color: "#27c2e8" }, { name: "Network", value: 32, color: "#3869e8" }, { name: "Commands", value: 16, color: "#8866f2" }, { name: "State", value: 8, color: "#4bc59f" }],
  "device-risk": [{ label: "CAM-01", Risk: 96 }, { label: "GW-01", Risk: 83 }, { label: "SEN-04", Risk: 61 }],
  "incident-timeline": incidentTimeline,
  "comparison-evidence": evidenceRows.slice(0, 3), "chronology-evidence": evidenceRows, "correlation-evidence": evidenceRows.slice(0, 3),
  "correlation-graph": { nodes: [{ id: "peer", label: "185.77.12.44", kind: "external", x: 8, y: 45 }, { id: "gateway", label: "GW-01", kind: "gateway", x: 40, y: 45 }, { id: "camera", label: "CAM-01", kind: "device", x: 76, y: 20 }, { id: "finding", label: "FND-1042", kind: "finding", x: 76, y: 70 }], edges: [{ from: "peer", to: "gateway", label: "42 connections" }, { from: "gateway", to: "camera", label: "auth + RTSP" }, { from: "gateway", to: "finding", label: "correlated" }] },
  "risk-factors": [{ label: "Rule confidence", value: 98 }, { label: "Asset criticality", value: 92 }, { label: "Temporal correlation", value: 97 }, { label: "Behavior deviation", value: 84 }],
  "primary-finding": { id: "FND-1042", title: "Credential attack followed by camera control", severity: "Critical", score: 96, text: "Authentication, connection, and command evidence are linked by the deterministic correlation pipeline." },
};
