export type Severity = "Critical" | "High" | "Medium" | "Low" | "Info";
type CaseType = "Batch" | "Live" | "Hybrid";

export interface InvestigationCase {
  id: string; name: string; reference: string; type: CaseType;
  status: "Active" | "Monitoring" | "Review" | "Closed";
  evidenceCount: number; findingsCount: number; deviceCount: number;
  risk: number; severity: Severity; updated: string; owner: string; description: string;
}
export interface Device {
  id: string; name: string; type: string; ip: string;
  status: "Online" | "Degraded" | "Offline"; risk: number;
  eventsPerMin: number; lastSeen: string;
}
export interface EvidenceRecord {
  id: string; timestamp: string; source: string; origin: "Batch" | "Live";
  device: string; eventType: string; severity: Severity; risk: number;
  raw: string; canonical: string; provenance: string; related: string[];
}
export interface Finding {
  id: string; title: string; summary: string; severity: Severity; risk: number; time: string;
  factors: { label: string; value: number }[]; trace: string[]; evidence: string[];
  devices: string[]; liveDetected?: boolean;
}
export interface Alert {
  id: string; title: string; severity: Severity; device: string; time: string;
  rule: string; status: "Open" | "Acknowledged" | "Escalated";
}
export interface LiveEvent {
  id: string; timestamp: string; device: string; eventType: string;
  sourceIp: string; origin: "Live"; severity: Severity; risk: number;
  normalized: boolean; provenance: string;
}
export interface TimelineEntry {
  id: string; time: string; title: string; description: string;
  type: "event" | "alert" | "finding" | "system"; severity: Severity; evidenceId?: string;
}
