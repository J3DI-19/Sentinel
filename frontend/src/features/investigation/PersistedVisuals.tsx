import { Background, Controls, MiniMap, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Area, AreaChart, Bar, BarChart, Brush, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { mapInvestigationRecords, type InvestigationRecordViewModel } from "./viewModels";

type ChartPoint = { series?: string; category?: string; subgroup?: string | null; value?: number };
type GraphNode = { node_id?: string; label?: string; kind?: string; event_count?: number; maximum_risk?: number };
type GraphEdge = { edge_id?: string; source_node_id?: string; target_node_id?: string; relationships?: string[]; event_count?: number };

const palette = ["#27c2e8", "#8b7cf6", "#f6b84a", "#fb6970", "#64d7aa", "#4d8dff"];
const tooltipStyle = { background: "#0b1322", border: "1px solid #263a55", borderRadius: 8, color: "#e4edf7", fontSize: 12 };
const label = (value: string) => value.replaceAll("_", " ");

export function PersistedVisuals({ points, nodes, edges, truncated }: { points: ChartPoint[]; nodes: GraphNode[]; edges: GraphEdge[]; truncated?: boolean }) {
  const series = (name: string) => points.filter(point => point.series === name && typeof point.value === "number");
  const attackClasses = series("attack_class");
  const eventTypes = (attackClasses.length ? attackClasses : series("event_type")).map(point => ({ name: label(point.category ?? "unknown"), value: point.value ?? 0 }));
  const severities = series("finding_severity").map((point, index) => ({ name: label(point.category ?? "unknown"), value: point.value ?? 0, fill: palette[index % palette.length] }));
  const riskBands = series("risk_band").map((point, index) => ({ name: label(point.category ?? "unknown"), value: point.value ?? 0, fill: palette[(index + 2) % palette.length] }));

  return <div className="persisted-visual-grid">
    <VisualPanel title={attackClasses.length ? "Attack classes" : "Event types"} description={attackClasses.length ? "Source classifications preserved during normalization." : "Canonical event composition."}>
      {eventTypes.length ? <div className="persisted-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={eventTypes}><CartesianGrid stroke="#1b2a40" vertical={false}/><XAxis dataKey="name" stroke="#71839a"/><YAxis stroke="#71839a" allowDecimals={false}/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="value" name="Events" fill="#27c2e8" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div> : <VisualEmpty text="No event-type aggregate is available."/>}
    </VisualPanel>
    <VisualPanel title="Finding severity" description="Distribution of persisted findings.">
      <Distribution rows={severities} empty="No findings are present in this snapshot."/>
    </VisualPanel>
    <VisualPanel title="Risk bands" description="Finding risk distribution.">
      <Distribution rows={riskBands} empty="No risk-band aggregate is available."/>
    </VisualPanel>
    <VisualPanel title="Entity relationships" description={`${nodes.length} persisted entities · ${edges.length} persisted relationships`} wide>
      <PersistedGraph nodes={nodes} edges={edges}/>
      {truncated && <p className="visual-warning">This graph is a partial view because backend safety limits were applied.</p>}
    </VisualPanel>
  </div>;
}

export function PersistedTimeline({ items, onInspect, page, windowsPerPage, onPage }: { items: Record<string, unknown>[]; onInspect: (item: InvestigationRecordViewModel) => void; page: number; windowsPerPage: number; onPage: (page: number) => void }) {
  const mapped = mapInvestigationRecords("timeline", items);
  if (!mapped.length) return <VisualEmpty text="No timestamped analysis or event records are available."/>;
  const groups = new Map<string, InvestigationRecordViewModel[]>();
  mapped.forEach(item => {
    const minute = timelineMinute(item.timestampUtc);
    groups.set(minute, [...(groups.get(minute) ?? []), item]);
  });
  const windows = Array.from(groups.entries());
  const totalPages = Math.max(1, Math.ceil(windows.length / windowsPerPage));
  const currentPage = Math.min(page, totalPages);
  const firstWindow = (currentPage - 1) * windowsPerPage;
  const visibleWindows = windows.slice(firstWindow, firstWindow + windowsPerPage);
  return <><ol className="persisted-timeline" aria-label="Chronological investigation timeline">{visibleWindows.map(([minute, group]) => {
    const first = group[0]; const last = group[group.length - 1];
    const categories = countBy(group, item => label(item.category ?? item.kind));
    const severities = group.map(item => item.severity).filter((value): value is string => Boolean(value));
    const peakSeverity = highestSeverity(severities);
    return <li key={minute} className="timeline-stop">
      <div className={`timeline-marker severity-${peakSeverity}`} aria-hidden="true"/>
      <div className="timeline-time"><time dateTime={first.timestampUtc ?? undefined}>{timelineTime(first.timestampUtc)}</time><span>{timelineDate(first.timestampUtc)}</span></div>
      <article className="timeline-card timeline-window">
        <header><div><span className="timeline-window-kicker">Minute window</span><strong>{group.length.toLocaleString()} persisted {group.length === 1 ? "record" : "records"}</strong></div><span>{timestampRange(first.timestampUtc, last.timestampUtc)}</span></header>
        <div className="timeline-composition" aria-label={`Composition of ${group.length} records`}>{categories.map(([category, count], index) => <span key={category} className={`timeline-segment timeline-segment-${index % 5}`} style={{ flexGrow: count }} title={`${category}: ${count}`}/>)}</div>
        <div className="timeline-kind-breakdown">{categories.map(([category, count], index) => <span key={category}><i className={`timeline-key timeline-key-${index % 5}`}/><b>{count.toLocaleString()}</b> {category}</span>)}</div>
        <details className="timeline-group"><summary><span>Review records in this minute</span><b>{group.length.toLocaleString()}</b></summary><div className="timeline-group-records">{group.map(item => <div key={item.id}><span><strong>{item.title}</strong><code>{item.id}</code></span><time>{timelineTimeWithSeconds(item.timestampUtc)}</time>{item.severity && <span className={`timeline-severity severity-${item.severity.toLowerCase()}`}>{item.severity}</span>}<button className="record-inspect" onClick={() => onInspect(item)} aria-label={`Inspect ${item.id}`}>Inspect</button></div>)}</div></details>
      </article>
    </li>;
  })}</ol>{windows.length > windowsPerPage && <div className="table-footer timeline-pagination"><div><button className="button button-secondary" disabled={currentPage === 1} onClick={() => onPage(1)}>First</button><button className="button button-secondary" disabled={currentPage === 1} onClick={() => onPage(currentPage - 1)}>Previous</button></div><span>Minute blocks <b>{firstWindow + 1}–{Math.min(firstWindow + windowsPerPage, windows.length)}</b> of <b>{windows.length}</b></span><div><button className="button button-secondary" disabled={currentPage >= totalPages} onClick={() => onPage(currentPage + 1)}>Next</button><button className="button button-secondary" disabled={currentPage >= totalPages} onClick={() => onPage(totalPages)}>Last</button></div></div>}</>;
}

export function TimelineActivityOverview({ points, total }: { points: ChartPoint[]; total: number }) {
  const activity = points.filter(point => point.series === "activity_minute" && typeof point.value === "number").sort((left, right) => Date.parse(left.category ?? "") - Date.parse(right.category ?? "")).map(point => ({ time: shortTime(point.category), value: point.value ?? 0 }));
  return <section className="timeline-overview"><header><div><span>Complete chronology</span><h2>Activity across the full snapshot</h2><p>{total.toLocaleString()} persisted entries are represented here. Drag the navigator beneath the chart to inspect dense periods; the chronological windows below provide individual records.</p></div></header>{activity.length ? <div className="timeline-overview-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={activity}><defs><linearGradient id="timelineActivity" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#27c2e8" stopOpacity={0.4}/><stop offset="1" stopColor="#27c2e8" stopOpacity={0}/></linearGradient></defs><CartesianGrid stroke="#1b2a40" vertical={false}/><XAxis dataKey="time" stroke="#71839a" minTickGap={30}/><YAxis stroke="#71839a" allowDecimals={false}/><Tooltip contentStyle={tooltipStyle}/><Area type="monotone" dataKey="value" name="Events" stroke="#27c2e8" strokeWidth={2} fill="url(#timelineActivity)"/><Brush dataKey="time" height={24} stroke="#27c2e8" fill="#0b1322" travellerWidth={8}/></AreaChart></ResponsiveContainer></div> : <VisualEmpty text="No complete-snapshot activity aggregate is available."/>}</section>;
}

export function IncidentContext({ items, onInspect }: { items: Record<string, unknown>[]; onInspect: (item: InvestigationRecordViewModel) => void }) {
  const mapped = mapInvestigationRecords("incidents", items);
  if (!mapped.length) return null;
  return <section className="incident-context"><header><div><span>Correlated context</span><h2>{mapped.length.toLocaleString()} incidents organize these findings</h2><p>Incidents group related events and findings. They are shown here as context rather than a separate investigation destination.</p></div></header><div className="incident-card-grid">{mapped.map(item => {
    const source = item.source as Record<string, unknown>; const findings = Array.isArray(source.finding_ids) ? source.finding_ids.length : 0; const events = Array.isArray(source.event_ids) ? source.event_ids.length : 0;
    return <article key={item.id} className="incident-context-card"><div><span className={`timeline-severity severity-${(item.severity ?? "high").toLowerCase()}`}>Risk {String(item.risk ?? source.maximum_risk ?? "—")}</span><code>{item.id}</code></div><h3>{findings} related finding{findings === 1 ? "" : "s"} · {events.toLocaleString()} events</h3><p>{String(source.started_at ?? "Start unavailable")} — {String(source.ended_at ?? "End unavailable")}</p><footer><span>{Number(source.correlation_edge_count ?? 0).toLocaleString()} correlations{source.correlation_edges_truncated ? " · references truncated" : ""}</span><button className="record-inspect" onClick={() => onInspect(item)} aria-label={`Inspect ${item.id}`}>Inspect incident</button></footer></article>;
  })}</div></section>;
}

function PersistedGraph({ nodes, edges }: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  if (!nodes.length) return <VisualEmpty text="No entities were derived from the selected evidence."/>;
  const flowNodes: Node[] = nodes.map((node, index) => ({ id: node.node_id ?? `node-${index}`, position: { x: (index % 4) * 210, y: Math.floor(index / 4) * 145 }, data: { label: `${node.label ?? node.node_id ?? "Entity"}\n${node.event_count ?? 0} events` }, style: { background: "#102238", border: `1px solid ${palette[index % palette.length]}`, borderRadius: 9, color: "#dce8f7", fontSize: 11, padding: 10, width: 170 } }));
  const known = new Set(flowNodes.map(node => node.id));
  const flowEdges: Edge[] = edges.filter(edge => edge.source_node_id && edge.target_node_id && known.has(edge.source_node_id) && known.has(edge.target_node_id)).map((edge, index) => ({ id: edge.edge_id ?? `edge-${index}`, source: edge.source_node_id!, target: edge.target_node_id!, label: edge.relationships?.join(", ") ?? "related", animated: false, style: { stroke: "#506783" }, labelStyle: { fill: "#94a7be", fontSize: 10 } }));
  return <><div className="persisted-graph" aria-label="Entity relationship graph"><ReactFlow nodes={flowNodes} edges={flowEdges} fitView colorMode="dark" nodesDraggable={false}><Background color="#24344a" gap={22}/><Controls/><MiniMap nodeColor="#27c2e8"/></ReactFlow></div>{flowEdges.length === 0 && <p className="visual-empty-note">One or more entities were identified, but this evidence contains no persisted relationships between them.</p>}</>;
}

function Distribution({ rows, empty }: { rows: { name: string; value: number; fill: string }[]; empty: string }) {
  if (!rows.length) return <VisualEmpty text={empty}/>;
  return <div className="persisted-distribution"><div className="persisted-pie"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={rows} dataKey="value" nameKey="name" innerRadius={52} outerRadius={78} paddingAngle={2}>{rows.map(row => <Cell key={row.name} fill={row.fill}/>)}</Pie><Tooltip contentStyle={tooltipStyle}/></PieChart></ResponsiveContainer></div><div className="visual-legend">{rows.map(row => <span key={row.name}><i style={{ background: row.fill }}/><span>{row.name}</span><b>{row.value.toLocaleString()}</b></span>)}</div></div>;
}

function VisualPanel({ title, description, wide = false, children }: { title: string; description: string; wide?: boolean; children: React.ReactNode }) { return <section className={`visual-data-panel${wide ? " visual-wide" : ""}`}><header><div><h2>{title}</h2><p>{description}</p></div><span>Persisted data</span></header>{children}</section>; }
function VisualEmpty({ text }: { text: string }) { return <div className="visual-empty"><span aria-hidden="true">◇</span><p>{text}</p></div>; }
function shortTime(value?: string) { if (!value) return "Unknown"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
function timelineMinute(value: string | null) { if (!value) return "Time unavailable"; const date = new Date(value); if (Number.isNaN(date.valueOf())) return value; date.setSeconds(0, 0); return date.toISOString().replace(":00.000Z", "Z"); }
function timelineTime(value: string | null) { if (!value) return "Unknown time"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
function timelineTimeWithSeconds(value: string | null) { if (!value) return "Unknown time"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? value : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); }
function timelineDate(value: string | null) { if (!value) return "Date unavailable"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? "Persisted timestamp" : date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }); }
function timestampRange(first: string | null, last: string | null) { return first === last ? (first ?? "Timestamp unavailable") : `${first ?? "Start unavailable"} — ${last ?? "End unavailable"}`; }
function countBy(items: InvestigationRecordViewModel[], key: (item: InvestigationRecordViewModel) => string) { const counts = new Map<string, number>(); items.forEach(item => { const value = key(item); counts.set(value, (counts.get(value) ?? 0) + 1); }); return Array.from(counts.entries()).sort((left, right) => right[1] - left[1]); }
function highestSeverity(values: string[]) { const order: Record<string, number> = { none: 0, low: 1, medium: 2, high: 3, critical: 4 }; return values.reduce((highest, value) => (order[value.toLowerCase()] ?? 0) > (order[highest] ?? 0) ? value.toLowerCase() : highest, "none"); }
