import { CaseAssistantWorkspace, type AssistantContextItem } from "../features/assistant/CaseAssistantWorkspace";
import { cases, findings } from "../mocks/data";

function contextFromQuery(params: URLSearchParams): AssistantContextItem[] {
  const keys = [{ key: "finding", kind: "Finding" }, { key: "alert", kind: "Alert" }, { key: "evidence", kind: "Evidence" }, { key: "device", kind: "Device" }];
  return keys.flatMap(item => { const value = params.get(item.key); return value ? [{ id: value, label: value, kind: item.kind }] : []; });
}

export function InvestigationAssistantPage({ navigate }: { navigate: (path: string) => void }) {
  const params = new URLSearchParams(window.location.search);
  const caseRef = params.get("case");
  const activeCase = cases.find(item => item.reference === caseRef || item.id === caseRef);
  const queryContext = contextFromQuery(params);
  if (activeCase) return <CaseAssistantWorkspace key={`${activeCase.reference}-${queryContext.map(item=>item.id).join("-")}`} navigate={navigate} caseReference={activeCase.reference} initialContext={queryContext}/>;

  return <div className="case-assistant-workspace central-assistant-default">
    <section className="assistant-column assistant-start-column">
      <header className="assistant-header"><div className="assistant-orb"><i/></div><div><span className="eyebrow">Central investigation workspace</span><h2>Investigation Assistant</h2><p>Explore cases and verified forensic evidence</p></div><span className="ai-status"><i/> Mock ready</span></header>
      <div className="assistant-empty-intro"><span>◎</span><h1>No investigation selected</h1><p>Select a case to ground the Assistant in one investigation and its preserved evidence.</p></div>
      <label className="assistant-case-picker"><span className="field-label">Select a case</span><select aria-label="Select an investigation" defaultValue="" onChange={event => event.target.value && navigate(`/assistant?case=${event.target.value}`)}><option value="" disabled>Choose an investigation…</option>{cases.map(item=><option key={item.id} value={item.reference}>{item.reference} · {item.name}</option>)}</select></label>
      <div className="assistant-recent-list"><span className="field-label">Recent cases</span>{cases.slice(0,3).map(item=><button key={item.id} onClick={()=>navigate(`/assistant?case=${item.reference}`)}><span>{item.type[0]}</span><div><b>{item.reference}</b><strong>{item.name}</strong><small>{item.updated} · {item.findingsCount} findings</small></div><em>Open →</em></button>)}</div>
      <div className="assistant-start-actions"><span className="field-label">Suggested starting actions</span><button onClick={()=>navigate("/cases")}>Search cases and evidence <span>→</span></button><button onClick={()=>navigate("/live")}>Review current live activity <span>→</span></button></div>
    </section>
    <section className="investigation-canvas assistant-start-canvas">
      <header className="canvas-header"><div><span className="eyebrow">Visual investigation</span><h2>Select an investigation to explore verified data</h2><p>Charts, timelines, device relationships, and evidence remain scoped to the active case.</p></div><span className="verified-data"><i/> Deterministic data references</span></header>
      <div className="assistant-start-grid">
        <section className="assistant-start-hero"><span>◎</span><h3>One workspace for investigative exploration</h3><p>Open a recent case or send a finding, alert, evidence record, or device here from its source workspace.</p><button onClick={()=>navigate(`/assistant?case=${cases[0].reference}`)}>Open most recent investigation →</button></section>
        <section><header><span className="field-label">Recent investigations</span></header>{cases.slice(0,3).map(item=><button key={item.id} onClick={()=>navigate(`/assistant?case=${item.reference}`)}><b>{item.reference}</b><span>{item.name}</span><small>{item.status} · {item.risk} risk</small></button>)}</section>
        <section><header><span className="field-label">Recent findings</span></header>{findings.slice(0,3).map(item=><button key={item.id} onClick={()=>navigate(`/assistant?case=${cases[0].reference}&finding=${item.id}`)}><b>{item.id}</b><span>{item.title}</span><small>{item.severity} · {item.risk} risk</small></button>)}</section>
        <section className="assistant-paths"><header><span className="field-label">Suggested investigation paths</span></header><div><span>01</span><p><b>Reconstruct chronology</b>Review events, alerts, and findings in preserved order.</p></div><div><span>02</span><p><b>Compare involved devices</b>Inspect activity and risk across related entities.</p></div><div><span>03</span><p><b>Explain correlation</b>Trace deterministic links back to evidence.</p></div></section>
      </div>
    </section>
  </div>;
}
