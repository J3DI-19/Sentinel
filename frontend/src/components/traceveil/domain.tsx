import type { Alert, Device, EvidenceRecord, Finding, LiveEvent, TimelineEntry } from "../../types/domain";
import { Button, Panel, RiskBadge, SeverityBadge, StatusBadge } from "../ui/core";

export function DeviceStatusCard({ device }: { device: Device }) {
  return <article className="device-card"><div className="device-icon">{device.type === "Gateway" ? "GW" : device.type.split(" ").map(w=>w[0]).join("").slice(0,2)}</div><div className="device-main"><strong>{device.name}</strong><span>{device.type} · {device.ip}</span><div><StatusBadge status={device.status} /><RiskBadge score={device.risk}/></div></div><div className="device-rate"><b>{device.eventsPerMin}</b><span>events/min</span></div></article>;
}
export function LiveEventFeed({ events }: { events: LiveEvent[] }) {
  return <div className="feed">{events.map(event => <div className="feed-row live-feed-row" key={event.id}><span className={`pulse-dot severity-${event.severity.toLowerCase()}`}/><code>{event.timestamp}</code><div className="feed-event-main"><strong>{event.eventType}</strong><span>{event.device} · {event.sourceIp}</span><div className="feed-indicators"><em>{event.normalized ? "✓ Canonical" : "Validation pending"}</em><em>Provenance · {event.provenance}</em></div></div><div className="feed-event-risk"><RiskBadge score={event.risk}/><SeverityBadge severity={event.severity}/></div></div>)}</div>;
}
export function LiveAlertFeed({ alerts, onInvestigate }: { alerts: Alert[]; onInvestigate?: (alert: Alert) => void }) {
  return <div className="alert-feed">{alerts.map(alert => <article className="alert-row" key={alert.id}><div><div className="alert-title"><SeverityBadge severity={alert.severity}/><strong>{alert.title}</strong></div><p>{alert.device} · {alert.rule}</p></div><div className="alert-meta"><time>{alert.time}</time><StatusBadge status={alert.status}/>{onInvestigate&&<button className="assistant-context-action" onClick={()=>onInvestigate(alert)}>Investigate with Assistant →</button>}</div></article>)}</div>;
}
export function RiskBreakdown({ factors }: { factors: Finding["factors"] }) {
  return <div className="risk-breakdown">{factors.map(f => <div key={f.label}><div><span>{f.label}</span><b>{f.value}</b></div><div className="bar"><i style={{width: `${f.value}%`}}/></div></div>)}</div>;
}
export function InvestigationTimeline({ entries }: { entries: TimelineEntry[] }) {
  return <div className="timeline">{entries.map((item)=><article className="timeline-entry" key={item.id}><div className={`timeline-marker timeline-${item.type}`}>{item.type === "alert" ? "!" : item.type === "finding" ? "◆" : "·"}</div><time>{item.time}</time><div><div><SeverityBadge severity={item.severity}/><span className="type-label">{item.type}</span>{item.evidenceId && <code>{item.evidenceId}</code>}</div><h3>{item.title}</h3><p>{item.description}</p></div></article>)}</div>;
}
export function EvidenceDetailPanel({ record, onClose, onInvestigate }: { record: EvidenceRecord | null; onClose?: () => void; onInvestigate?: (record: EvidenceRecord) => void }) {
  if (!record) return <Panel className="detail-empty"><div className="state-box"><span>⌖</span><strong>Select an evidence record</strong><p>Review the raw record, canonical normalization, provenance, and investigation references.</p></div></Panel>;
  return <aside className="evidence-detail"><div className="detail-head"><div><span className="eyebrow">Evidence detail</span><h2>{record.id}</h2></div>{onClose && <Button variant="ghost" onClick={onClose}>×</Button>}</div><div className="detail-summary"><SeverityBadge severity={record.severity}/><RiskBadge score={record.risk}/><span>{record.origin}</span></div><dl><div><dt>Observed</dt><dd>{record.timestamp}</dd></div><div><dt>Device</dt><dd>{record.device}</dd></div><div><dt>Event type</dt><dd>{record.eventType}</dd></div></dl><div className="code-block"><span>Raw source record</span><pre>{record.raw}</pre></div><div className="code-block canonical"><span>Canonical event</span><pre>{record.canonical}</pre></div><div className="detail-section"><span className="field-label">Source provenance</span><p>{record.provenance}</p></div><div className="reference-row"><span>Related references</span>{record.related.map(r=><code key={r}>{r}</code>)}</div>{onInvestigate&&<Button onClick={()=>onInvestigate(record)}>Investigate in Assistant →</Button>}</aside>;
}
