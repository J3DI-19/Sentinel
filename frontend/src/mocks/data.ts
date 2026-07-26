import type { Alert, Device, EvidenceRecord, Finding, InvestigationCase, LiveEvent, TimelineEntry } from "../types/domain";

export const cases: InvestigationCase[] = [
  { id: "case-024", reference: "TV-2026-024", name: "Northbridge Camera Intrusion", type: "Hybrid", status: "Active", evidenceCount: 18420, findingsCount: 12, deviceCount: 8, risk: 91, severity: "Critical", updated: "2 min ago", owner: "Investigator", description: "Coordinated authentication failures and outbound command traffic across the Northbridge residence camera network." },
  { id: "case-023", reference: "TV-2026-023", name: "Thermostat Beaconing Review", type: "Batch", status: "Review", evidenceCount: 9241, findingsCount: 5, deviceCount: 3, risk: 72, severity: "High", updated: "38 min ago", owner: "Arjun Rao", description: "Historical analysis of regular outbound connections from a compromised thermostat." },
  { id: "case-021", reference: "TV-2026-021", name: "Gateway Rate Anomaly", type: "Live", status: "Monitoring", evidenceCount: 4820, findingsCount: 3, deviceCount: 11, risk: 64, severity: "Medium", updated: "1 hr ago", owner: "Nina Patel", description: "Controlled monitoring of elevated request volume at the lab gateway." },
  { id: "case-019", reference: "TV-2026-019", name: "Smart Plug Command Sequence", type: "Batch", status: "Closed", evidenceCount: 6112, findingsCount: 7, deviceCount: 4, risk: 48, severity: "Low", updated: "Jul 18", owner: "Investigator", description: "Validated command sequence reconstructed from TON_IoT evidence." },
];

export const devices: Device[] = [
  { id: "dev-cam-01", name: "Camera · Entryway", type: "Smart Camera", ip: "10.42.0.18", status: "Online", risk: 94, eventsPerMin: 48, lastSeen: "4s ago" },
  { id: "dev-gw-01", name: "Gateway · Northbridge", type: "Gateway", ip: "10.42.0.1", status: "Online", risk: 79, eventsPerMin: 132, lastSeen: "now" },
  { id: "dev-door-02", name: "Door Sensor · Patio", type: "Smart Door Sensor", ip: "10.42.0.24", status: "Degraded", risk: 67, eventsPerMin: 9, lastSeen: "42s ago" },
  { id: "dev-voice-01", name: "Voice Hub · Kitchen", type: "Voice Assistant", ip: "10.42.0.31", status: "Online", risk: 28, eventsPerMin: 17, lastSeen: "8s ago" },
  { id: "dev-plug-03", name: "Smart Plug · Office", type: "Smart Plug", ip: "10.42.0.42", status: "Offline", risk: 54, eventsPerMin: 0, lastSeen: "12m ago" },
  { id: "dev-therm-01", name: "Thermostat · Hallway", type: "Thermostat", ip: "10.42.0.36", status: "Online", risk: 41, eventsPerMin: 6, lastSeen: "19s ago" },
];

export const evidence: EvidenceRecord[] = [
  { id: "EVD-2026-8F21", timestamp: "2026-07-21 14:32:08.441", source: "Northbridge collector", origin: "Live", device: "Camera · Entryway", eventType: "authentication_failure", severity: "Critical", risk: 96, raw: "{ src_ip: '185.77.12.44', user: 'admin', result: 'denied', attempts: 14 }", canonical: "{ actor: '185.77.12.44', target: 'dev-cam-01', action: 'authenticate', outcome: 'failure' }", provenance: "MQTT lab collector · topic /northbridge/camera/auth · SHA-256 8f21…d09a", related: ["FND-1042", "ALT-8831", "TL-401"] },
  { id: "EVD-2026-8F20", timestamp: "2026-07-21 14:31:54.103", source: "Northbridge collector", origin: "Live", device: "Gateway · Northbridge", eventType: "unusual_request_rate", severity: "High", risk: 83, raw: "{ requests: 132, window_s: 60, baseline: 24 }", canonical: "{ target: 'dev-gw-01', metric: 'request_rate', value: 132, baseline: 24 }", provenance: "Gateway telemetry · immutable capture segment live-0721-14", related: ["FND-1041", "ALT-8829"] },
  { id: "EVD-2026-8F19", timestamp: "2026-07-21 14:31:41.772", source: "TON_IoT import", origin: "Batch", device: "Camera · Entryway", eventType: "connection_attempt", severity: "High", risk: 78, raw: "ts,src_ip,dst_ip,dst_port,proto,label\n...,185.77.12.44,10.42.0.18,554,tcp,scanning", canonical: "{ actor: '185.77.12.44', target: 'dev-cam-01', action: 'connect', dst_port: 554 }", provenance: "northbridge-toniot.csv · row 18,224 · SHA-256 11c4…82fe", related: ["FND-1042", "TL-398"] },
  { id: "EVD-2026-8F18", timestamp: "2026-07-21 14:30:12.004", source: "Northbridge collector", origin: "Live", device: "Door Sensor · Patio", eventType: "device_offline", severity: "Medium", risk: 61, raw: "{ heartbeat: false, missed_intervals: 3 }", canonical: "{ target: 'dev-door-02', action: 'heartbeat', outcome: 'timeout' }", provenance: "MQTT lab collector · topic /northbridge/door/status", related: ["ALT-8827", "TL-396"] },
  { id: "EVD-2026-8F17", timestamp: "2026-07-21 14:29:47.668", source: "CICIoT2023 import", origin: "Batch", device: "Smart Plug · Office", eventType: "command_request", severity: "Low", risk: 33, raw: "{ command: 'power_cycle', user: 'automation', status: 200 }", canonical: "{ actor: 'automation', target: 'dev-plug-03', action: 'power_cycle', outcome: 'success' }", provenance: "ciciot-slice-04.parquet · record 7712", related: ["TL-392"] },
];

export const findings: Finding[] = [
  { id: "FND-1042", title: "Credential attack followed by camera control traffic", summary: "Fourteen failed admin logins from an external host were followed by a successful session and an RTSP command sequence within 74 seconds.", severity: "Critical", risk: 96, time: "14:33", factors: [{ label: "Rule confidence", value: 98 }, { label: "Asset criticality", value: 92 }, { label: "Temporal correlation", value: 97 }], trace: ["External authentication failures ≥ 10", "Successful login within 120 seconds", "Privileged camera command observed", "Same actor IP across all events"], evidence: ["EVD-2026-8F21", "EVD-2026-8F19", "EVD-2026-8F14"], devices: ["Camera · Entryway", "Gateway · Northbridge"], liveDetected: true },
  { id: "FND-1041", title: "Gateway request rate exceeds learned baseline", summary: "The Northbridge gateway emitted 5.5× its established one-minute request baseline, concentrated on two internal targets.", severity: "High", risk: 83, time: "14:32", factors: [{ label: "Volume deviation", value: 91 }, { label: "Target spread", value: 72 }, { label: "Persistence", value: 76 }], trace: ["Request rate > 4× baseline", "Window duration ≥ 60 seconds", "More than one internal target"], evidence: ["EVD-2026-8F20", "EVD-2026-8F16"], devices: ["Gateway · Northbridge"], liveDetected: true },
  { id: "FND-1038", title: "Door sensor availability gap", summary: "Three heartbeat intervals were missed during the authentication sequence, creating a 92-second visibility gap.", severity: "Medium", risk: 61, time: "14:30", factors: [{ label: "Visibility loss", value: 73 }, { label: "Temporal relevance", value: 68 }, { label: "Asset criticality", value: 45 }], trace: ["Heartbeat missing ≥ 3 intervals", "Concurrent high-risk activity"], evidence: ["EVD-2026-8F18"], devices: ["Door Sensor · Patio"] },
];

export const alerts: Alert[] = [
  { id: "ALT-8831", title: "Repeated privileged authentication failures", severity: "Critical", device: "Camera · Entryway", time: "14:32:08", rule: "AUTH-014 · 10 failures / 60s", status: "Escalated" },
  { id: "ALT-8829", title: "Request rate baseline exceeded", severity: "High", device: "Gateway · Northbridge", time: "14:31:54", rule: "NET-009 · rate > 4× baseline", status: "Open" },
  { id: "ALT-8827", title: "Critical sensor heartbeat missed", severity: "Medium", device: "Door Sensor · Patio", time: "14:30:12", rule: "DEV-002 · 3 missed intervals", status: "Acknowledged" },
  { id: "ALT-8824", title: "Outbound connection to rare host", severity: "High", device: "Thermostat · Hallway", time: "14:27:44", rule: "NET-021 · destination rarity", status: "Open" },
];

export const liveEvents: LiveEvent[] = [
  { id: "LE-99182", timestamp: "14:32:31.204", device: "Camera · Entryway", eventType: "command_request", sourceIp: "185.77.12.44", origin: "Live", severity: "Critical", risk: 96, normalized: true, provenance: "live-lab-01" },
  { id: "LE-99181", timestamp: "14:32:28.771", device: "Gateway · Northbridge", eventType: "connection_attempt", sourceIp: "185.77.12.44", origin: "Live", severity: "High", risk: 83, normalized: true, provenance: "live-lab-01" },
  { id: "LE-99180", timestamp: "14:32:21.065", device: "Voice Hub · Kitchen", eventType: "status_change", sourceIp: "10.42.0.31", origin: "Live", severity: "Info", risk: 18, normalized: true, provenance: "live-lab-01" },
  { id: "LE-99179", timestamp: "14:32:08.441", device: "Camera · Entryway", eventType: "authentication_failure", sourceIp: "185.77.12.44", origin: "Live", severity: "Critical", risk: 94, normalized: true, provenance: "live-lab-01" },
  { id: "LE-99178", timestamp: "14:31:54.103", device: "Gateway · Northbridge", eventType: "unusual_request_rate", sourceIp: "10.42.0.1", origin: "Live", severity: "High", risk: 79, normalized: true, provenance: "live-lab-01" },
  { id: "LE-99177", timestamp: "14:31:41.990", device: "Thermostat · Hallway", eventType: "status_change", sourceIp: "10.42.0.36", origin: "Live", severity: "Low", risk: 31, normalized: true, provenance: "live-lab-01" },
];

export const timeline: TimelineEntry[] = [
  { id: "TL-392", time: "14:29:47", title: "Routine smart plug power cycle", description: "Scheduled automation issued a successful power-cycle command.", type: "event", severity: "Low", evidenceId: "EVD-2026-8F17" },
  { id: "TL-396", time: "14:30:12", title: "Patio sensor stopped reporting", description: "Three expected heartbeat packets were not observed.", type: "alert", severity: "Medium", evidenceId: "EVD-2026-8F18" },
  { id: "TL-398", time: "14:31:41", title: "External actor connected to camera RTSP", description: "Connection from 185.77.12.44 matched historical batch evidence.", type: "event", severity: "High", evidenceId: "EVD-2026-8F19" },
  { id: "TL-400", time: "14:31:54", title: "Gateway request-rate rule triggered", description: "132 requests/min observed against a baseline of 24.", type: "alert", severity: "High", evidenceId: "EVD-2026-8F20" },
  { id: "TL-401", time: "14:32:08", title: "Authentication threshold crossed", description: "Fourteenth failed administrator login triggered AUTH-014.", type: "alert", severity: "Critical", evidenceId: "EVD-2026-8F21" },
  { id: "TL-404", time: "14:33:22", title: "Correlated finding created", description: "Deterministic pipeline linked authentication, connection, and command evidence.", type: "finding", severity: "Critical" },
];

export const activityData = [
  { time: "13:40", batch: 42, live: 18 }, { time: "13:50", batch: 38, live: 24 },
  { time: "14:00", batch: 46, live: 31 }, { time: "14:10", batch: 41, live: 28 },
  { time: "14:20", batch: 55, live: 46 }, { time: "14:30", batch: 63, live: 118 },
  { time: "14:40", batch: 49, live: 86 },
];
export const severityData = [
  { name: "Critical", value: 8, color: "#fb5f68" }, { name: "High", value: 18, color: "#ff9f43" },
  { name: "Medium", value: 31, color: "#e8c547" }, { name: "Low", value: 27, color: "#35bde8" },
];
export const riskData = [
  { band: "0–25", events: 420 }, { band: "26–50", events: 284 }, { band: "51–75", events: 146 }, { band: "76–100", events: 62 },
];
export const deviceActivity = [
  { name: "Gateway", events: 322 }, { name: "Camera", events: 248 }, { name: "Door", events: 121 }, { name: "Voice hub", events: 94 }, { name: "Thermostat", events: 66 },
];
export const categoryData = [
  { name: "Authentication", value: 28 }, { name: "Network", value: 34 }, { name: "Command", value: 17 }, { name: "State", value: 21 },
];

export const graphNodes = [
  { id: "internet", position: { x: 30, y: 175 }, data: { label: "185.77.12.44\nExternal actor", kind: "external", risk: 96 }, type: "default" },
  { id: "gateway", position: { x: 290, y: 175 }, data: { label: "Northbridge Gateway", kind: "gateway", risk: 79 } },
  { id: "camera", position: { x: 570, y: 45 }, data: { label: "Entryway Camera", kind: "device", risk: 94 } },
  { id: "door", position: { x: 570, y: 175 }, data: { label: "Patio Door Sensor", kind: "device", risk: 67 } },
  { id: "thermostat", position: { x: 570, y: 305 }, data: { label: "Hallway Thermostat", kind: "device", risk: 41 } },
];
export const graphEdges = [
  { id: "e1", source: "internet", target: "gateway", label: "42 connections", animated: true },
  { id: "e2", source: "gateway", target: "camera", label: "auth + RTSP", animated: true },
  { id: "e3", source: "gateway", target: "door", label: "heartbeat" },
  { id: "e4", source: "gateway", target: "thermostat", label: "telemetry" },
];
