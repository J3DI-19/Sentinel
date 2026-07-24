import { alerts, cases, devices, severityData } from "../mocks/data";
import { Button, MetricCard, PageHeader, Panel, RiskBadge, SeverityBadge, StatusBadge } from "../components/ui/core";
import { VisualizationRenderer } from "../visualizations/VisualizationRenderer";

export function OverviewCommandCenter({ navigate }: { navigate: (path: string) => void }) {
  return <>
    <PageHeader eyebrow="Command center · 21 July 2026" title="Investigation overview" description="The overall state of Traceveil, preserved evidence, and active investigations." actions={<><Button onClick={() => navigate("/import")}>⇧ Import evidence</Button><Button variant="primary" onClick={() => navigate("/cases/case-024")}>Open active case →</Button></>}/>
    <section className="overview-status" aria-label="Operational status">
      <div><span className="signal live"/><span>Collector</span><b>Operational</b></div>
      <div><span className="signal live"/><span>Backend API</span><b>Connected</b></div>
      <div><span className="signal cyan"/><span>Devices</span><b>17 / 19 online</b></div>
      <div><span className="signal cyan"/><span>Last live event</span><b>4 seconds ago</b></div>
    </section>
    <div className="metrics-grid four overview-metrics">
      <MetricCard label="Active cases" value="04" detail="1 critical" trend="+1 this week" icon="□"/>
      <MetricCard label="Stored evidence" value="38.6K" detail="canonical events" trend="+6.2%" icon="▤"/>
      <MetricCard label="Open findings" value="20" detail="across 3 cases" trend="12 high+" icon="◆"/>
      <MetricCard label="Critical alerts" value="03" detail="unresolved environment-wide" tone="danger" icon="!"/>
    </div>
    <div className="overview-grid">
      <Panel className="overview-activity" title="Event activity" action={<div className="chart-legend"><span className="blue">Batch evidence</span><span className="cyan">Live telemetry</span><select aria-label="Event activity period"><option>Last hour</option></select></div>}><div className="chart-large"><VisualizationRenderer type="eventActivity"/></div></Panel>
      <Panel title="Severity distribution"><div className="donut-wrap"><div className="chart-donut"><VisualizationRenderer type="severityDistribution"/><div className="donut-total"><b>{severityData.reduce((a,b)=>a+b.value,0)}</b><span>findings</span></div></div><div className="legend-list">{severityData.map(d=><div key={d.name}><i style={{background:d.color}}/><span>{d.name}</span><b>{d.value}</b></div>)}</div></div></Panel>
      <Panel className="overview-alerts" title="Recent alerts" action={<button className="text-button" onClick={() => navigate("/live")}>View live monitor →</button>}><div className="compact-alerts">{alerts.slice(0,3).map(a=><div key={a.id}><SeverityBadge severity={a.severity}/><div><strong>{a.title}</strong><span>{a.device} · {a.rule}</span></div><time>{a.time}</time><StatusBadge status={a.status}/></div>)}</div></Panel>
      <Panel title="Top device risk"><div className="risk-list">{devices.slice(0,4).map((d,i)=><div key={d.id}><span>{String(i+1).padStart(2,"0")}</span><div><strong>{d.name}</strong><small>{d.type} · {d.status}</small></div><RiskBadge score={d.risk}/></div>)}</div></Panel>
      <Panel className="overview-cases" title="Recent cases" action={<button className="text-button" onClick={() => navigate("/cases")}>All cases →</button>}><div className="recent-cases">{cases.slice(0,3).map(c=><button key={c.id} onClick={() => navigate(`/cases/${c.id}`)}><div className="case-initial">{c.type.slice(0,1)}</div><div><span>{c.reference}</span><strong>{c.name}</strong></div><StatusBadge status={c.status}/><span>{c.evidenceCount.toLocaleString()} evidence</span><RiskBadge score={c.risk}/><em>→</em></button>)}</div></Panel>
    </div>
  </>;
}
