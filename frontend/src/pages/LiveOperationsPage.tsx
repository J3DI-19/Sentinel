import { alerts, devices, liveEvents } from "../mocks/data";
import { DeviceStatusCard, LiveAlertFeed, LiveEventFeed } from "../components/traceveil/domain";
import { Button, MetricCard, PageHeader, Panel } from "../components/ui/core";
import { VisualizationRenderer } from "../visualizations/VisualizationRenderer";

export function LiveOperationsPage({ navigate }: { navigate:(path:string)=>void }) {
  return <>
    <PageHeader eyebrow="Controlled telemetry · Current session" title="Live monitor" description="What is happening right now across the controlled live environment." actions={<><Button>Pause feed</Button><Button variant="primary" onClick={() => navigate("/cases/case-024/live")}>Open case capture →</Button></>}/>
    <div className="connection-banner live-connection-detail">
      <div className="radar-icon"><i/><i/><span/></div>
      <div className="connection-copy"><span className="eyebrow">Collector connection</span><h3 className="collector-primary-state"><i/> Live · Capturing</h3><p>Telemetry is being validated and normalized into canonical events.</p></div>
      <div className="connection-stats"><span><b>live-lab-01</b>Collector ID</span><span><b>00:47:18</b>Session duration</span><span><b>4s ago</b>Last event</span></div>
    </div>
    <div className="metrics-grid four"><MetricCard label="Devices online" value="17 / 19" detail="2 require attention" tone="cyan"/><MetricCard label="Events / minute" value="86" trend="↑ 177% vs baseline"/><MetricCard label="Active alerts" value="4" detail="1 critical" tone="danger"/><MetricCard label="Malformed events" value="3" detail="0.04% of stream"/></div>
    <Panel className="live-activity-panel" title="Live event activity" action={<div className="chart-legend"><span className="cyan">Current-session canonical events</span><span>Last 60 minutes</span></div>}><div className="chart-medium"><VisualizationRenderer type="eventActivity"/></div></Panel>
    <div className="monitoring-semantics"><span>Detection model</span><div><b>Event</b><small>Activity</small></div><i>→</i><div><b>Alert</b><small>Rule match</small></div><i>→</i><div><b>Finding</b><small>Investigation unit</small></div><button aria-label="Explain detection model" title={'Event: Something happened on a device or network.\n\nAlert: A deterministic detection rule matched event conditions.\n\nFinding: Evidence, risk factors, alerts, and investigative context form a reviewable investigation unit.'}>i</button></div>
    <div className="live-grid refined live-feed-grid">
      <Panel className="span-2" title="Live event feed" action={<div className="feed-tools"><span className="streaming">● Streaming mock data</span><button>Filter</button></div>}><LiveEventFeed events={liveEvents}/></Panel>
      <Panel title="Live alerts · Current session" action={<button className="text-button">Rule registry →</button>}><LiveAlertFeed alerts={alerts.slice(0,3)} onInvestigate={alert=>navigate(`/assistant?case=TV-2026-024&alert=${alert.id}`)}/></Panel>
    </div>
    <div className="section-header compact"><div><h2>Device status</h2><p>Inventory health and live traffic volume for the current collector scope.</p></div><button className="text-button">View inventory →</button></div>
    <div className="device-grid">{devices.map(d=><DeviceStatusCard key={d.id} device={d}/>)}</div>
  </>;
}
