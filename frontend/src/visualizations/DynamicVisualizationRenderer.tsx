import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { InvestigationTimeline, RiskBreakdown } from "../components/traceveil/domain";
import { MetricCard, RiskBadge, SeverityBadge } from "../components/ui/core";
import { visualizationDatasets, type VisualizationComponentSpec, type VisualizationSpec } from "../mocks/assistant";
import type { Severity, TimelineEntry } from "../types/domain";

const tooltipStyle = { background: "#0b1322", border: "1px solid #21304a", borderRadius: 8, color: "#dce8f7", fontSize: 11 };
type RendererProps = { data: unknown; spec: VisualizationComponentSpec };
type ChartRow = Record<string, string | number>;

function Metric({ data, spec }: RendererProps) {
  const item = data as { value: string; detail: string; tone?: "danger" | "cyan" };
  return <MetricCard label={spec.title} value={item.value} detail={item.detail} tone={item.tone}/>;
}

function MultiBar({ data }: RendererProps) {
  const rows = data as ChartRow[]; const keys = Object.keys(rows[0] || {}).filter(k => k !== "label");
  return <div className="dynamic-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows}><CartesianGrid stroke="#18253a" vertical={false}/><XAxis dataKey="label" stroke="#63738a" tickLine={false}/><YAxis stroke="#63738a" tickLine={false}/><Tooltip contentStyle={tooltipStyle}/>{keys.map((key,index)=><Bar key={key} dataKey={key} fill={["#27c2e8","#3869e8","#8866f2"][index]} radius={[5,5,0,0]}/>)}</BarChart></ResponsiveContainer></div>;
}

function ActivityArea({ data }: RendererProps) {
  return <div className="dynamic-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data as ChartRow[]}><defs><linearGradient id="areaEvents" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#27c2e8" stopOpacity=".4"/><stop offset="1" stopColor="#27c2e8" stopOpacity="0"/></linearGradient></defs><CartesianGrid stroke="#18253a" vertical={false}/><XAxis dataKey="label" stroke="#63738a" tickLine={false}/><YAxis stroke="#63738a" tickLine={false}/><Tooltip contentStyle={tooltipStyle}/><Area type="monotone" dataKey="Events" stroke="#27c2e8" fill="url(#areaEvents)" strokeWidth={2}/><Area type="monotone" dataKey="Alerts" stroke="#fb5f68" fill="transparent" strokeWidth={2}/></AreaChart></ResponsiveContainer></div>;
}

function Distribution({ data }: RendererProps) {
  const rows = data as { name: string; value: number; color: string }[];
  return <div className="dynamic-pie"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={rows} dataKey="value" nameKey="name" innerRadius={38} outerRadius={62} paddingAngle={3}>{rows.map(row=><Cell key={row.name} fill={row.color}/>)}</Pie><Tooltip contentStyle={tooltipStyle}/></PieChart></ResponsiveContainer><div className="mini-legend">{rows.map(row=><span key={row.name}><i style={{background:row.color}}/>{row.name} <b>{row.value}%</b></span>)}</div></div>;
}

function EvidenceTable({ data }: RendererProps) {
  const rows = data as { id:string; time:string; device:string; event:string; severity:Severity }[];
  return <div className="dynamic-table-wrap"><table className="dynamic-table"><thead><tr><th>Time</th><th>Evidence</th><th>Device</th><th>Event</th><th>Severity</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td><code>{row.time}</code></td><td><code>{row.id}</code></td><td>{row.device}</td><td>{row.event}</td><td><SeverityBadge severity={row.severity}/></td></tr>)}</tbody></table></div>;
}

function AlertList({ data }: RendererProps) {
  const rows = data as { id:string; time:string; title:string; severity:Severity; risk:number; status:string }[];
  return <div className="dynamic-table-wrap"><table className="dynamic-table"><thead><tr><th>Time</th><th>Alert</th><th>Severity</th><th>Risk</th><th>Status</th></tr></thead><tbody>{rows.map(row=><tr key={row.id}><td><code>{row.time}</code></td><td>{row.title}</td><td><SeverityBadge severity={row.severity}/></td><td><RiskBadge score={row.risk}/></td><td>{row.status}</td></tr>)}</tbody></table></div>;
}

function Timeline({ data }: RendererProps) { return <div className="dynamic-timeline"><InvestigationTimeline entries={data as TimelineEntry[]}/></div>; }

function Summary({ data }: RendererProps) {
  const item = data as { lead:string; text:string; refs:string[] };
  return <div className="visual-summary"><span>✓ {item.lead}</span><p>{item.text}</p><div>{item.refs.map(ref=><code key={ref}>{ref}</code>)}</div></div>;
}

function Finding({ data }: RendererProps) {
  const item = data as { id:string; title:string; severity:Severity; score:number; text:string };
  return <div className="visual-finding"><div><code>{item.id}</code><SeverityBadge severity={item.severity}/></div><h4>{item.title}</h4><p>{item.text}</p><RiskBadge score={item.score}/></div>;
}

function Risk({ data }: RendererProps) { return <RiskBreakdown factors={data as {label:string;value:number}[]}/>; }

function DeviceGraph({ data }: RendererProps) {
  const graph = data as { nodes:{id:string;label:string;kind:string;x:number;y:number}[]; edges:{from:string;to:string;label:string}[] };
  const node = (id:string) => graph.nodes.find(n => n.id === id)!;
  return <div className="dynamic-graph"><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Correlation graph">{graph.edges.map(edge=>{const from=node(edge.from),to=node(edge.to);return <g key={`${edge.from}-${edge.to}`}><line x1={from.x+6} y1={from.y} x2={to.x} y2={to.y} /><text x={(from.x+to.x)/2} y={(from.y+to.y)/2-2}>{edge.label}</text></g>})}</svg>{graph.nodes.map(n=><div key={n.id} className={`graph-chip graph-${n.kind}`} style={{left:`${n.x}%`,top:`${n.y}%`}}><i/>{n.label}<small>{n.kind}</small></div>)}</div>;
}

const dynamicVisualizationRegistry: Record<string, (props: RendererProps) => React.JSX.Element> = {
  "metric-card": Metric, "bar-chart": MultiBar, "line-chart": ActivityArea, "area-chart": ActivityArea, "pie-chart": Distribution,
  "evidence-table": EvidenceTable, "investigation-timeline": Timeline, "device-graph": DeviceGraph,
  "finding-panel": Finding, "risk-breakdown": Risk, "text-summary": Summary,
  "timeline": Timeline, "risk_breakdown": Risk, "event_activity": ActivityArea,
  "entity_graph": DeviceGraph, "evidence_table": EvidenceTable, "alert_list": AlertList,
};

function VisualizationFallback({ spec, reason }: { spec: VisualizationComponentSpec; reason: "unknown-component" | "missing-data" }) {
  return <div className="visualization-fallback" role="status"><span>◇</span><strong>Visualization unavailable</strong><p>{reason === "unknown-component" ? `“${spec.type}” is not in the approved registry.` : `Dataset “${spec.dataRef}” could not be resolved.`}</p></div>;
}

export function DynamicVisualizationRenderer({ specification, datasets = visualizationDatasets }: { specification: VisualizationSpec; datasets?: Record<string, unknown> }) {
  return <div className="dynamic-layout" key={specification.id}>{specification.components.map(spec => {
    const Component = dynamicVisualizationRegistry[spec.type]; const data = datasets[spec.dataRef];
    return <section className={`visual-panel visual-span-${spec.span || 1} visual-height-${spec.height || "standard"}`} key={spec.id}><header><div><span>Verified data view</span><h3>{spec.title}</h3></div><code>{spec.type}</code></header><div className="visual-panel-body">{!Component ? <VisualizationFallback spec={spec} reason="unknown-component"/> : data === undefined ? <VisualizationFallback spec={spec} reason="missing-data"/> : <Component data={data} spec={spec}/>}</div></section>;
  })}</div>;
}
