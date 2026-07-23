import { useState } from "react";
import { Background, Controls, MiniMap, ReactFlow, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { graphEdges, graphNodes } from "../../mocks/data";
import { RiskBadge } from "../../components/ui/core";

export function DeviceGraphPanel() {
  const [selected, setSelected] = useState<Node>(graphNodes[1] as Node);
  return <div className="graph-layout"><div className="graph-canvas"><div className="graph-toolbar"><span><i className="legend-device"/>Device</span><span><i className="legend-gateway"/>Gateway</span><span><i className="legend-external"/>External entity</span><b>5 entities · 4 relations</b></div><ReactFlow nodes={graphNodes} edges={graphEdges} fitView onNodeClick={(_, node)=>setSelected(node)} colorMode="dark"><Background color="#1b2a40" gap={22}/><Controls/><MiniMap nodeColor={(node)=>node.id === "internet" ? "#fb5f68" : node.id === "gateway" ? "#3869e8" : "#27c2e8"}/></ReactFlow></div><aside className="graph-detail"><span className="eyebrow">Selected entity</span><div className="entity-icon">{selected.id === "internet" ? "IP" : selected.id === "gateway" ? "GW" : "IO"}</div><h2>{String(selected.data.label).split("\n")[0]}</h2><p>{selected.id === "internet" ? "External network entity observed in both imported and live evidence." : "Known Northbridge inventory entity with preserved network identity."}</p><RiskBadge score={Number(selected.data.risk)}/><dl><div><dt>Entity ID</dt><dd>{selected.id}</dd></div><div><dt>Relations</dt><dd>{graphEdges.filter(e=>e.source===selected.id||e.target===selected.id).length}</dd></div><div><dt>Evidence refs</dt><dd>6 linked</dd></div></dl><button className="button button-secondary">View related evidence</button></aside></div>;
}
