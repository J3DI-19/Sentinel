import { useState } from "react";
import { Button } from "../../components/ui/core";
import { assistantContext, assistantPrompts, initialAssistantMessages, visualizationSpecs, type AssistantMessageData } from "../../mocks/assistant";
import { DynamicVisualizationRenderer } from "../../visualizations/DynamicVisualizationRenderer";
import { cases } from "../../mocks/data";

export interface AssistantContextItem { id: string; label: string; kind: string; }

function EvidenceReferenceChip({ reference }: { reference: string }) { return <button className="evidence-reference" title={`Open ${reference}`}>{reference}<span>↗</span></button>; }

function ConversationMessage({ message }: { message: AssistantMessageData }) {
  const assistant = message.role === "assistant";
  return <article className={`assistant-message assistant-message-${message.role}`}><div className="message-avatar">{assistant ? "TV" : "IN"}</div><div className="message-content"><div className="message-byline"><b>{assistant ? "Traceveil Assistant" : "Investigator"}</b>{assistant && <span className={`message-kind kind-${message.kind}`}>{message.kind === "verified" ? "✓ Verified evidence" : "AI narration"}</span>}</div><p>{message.text}</p>{message.references && <div className="assistant-references">{message.references.map(ref=><EvidenceReferenceChip key={ref} reference={ref}/>)}</div>}</div></article>;
}

export function CaseAssistantWorkspace({ navigate, caseReference = "TV-2026-024", initialContext = assistantContext }: { navigate?: (path: string) => void; caseReference?: string; initialContext?: AssistantContextItem[] }) {
  const activeCase = cases.find(item => item.reference === caseReference || item.id === caseReference) || cases[0];
  const [messages, setMessages] = useState(initialAssistantMessages);
  const [context, setContext] = useState(initialContext);
  const [specId, setSpecId] = useState("incident-context");
  const [value, setValue] = useState("");
  const [compact, setCompact] = useState(false);
  const specification = visualizationSpecs[specId] || visualizationSpecs["incident-context"];
  const runPrompt = (promptId: string, override?: string) => {
    const prompt = assistantPrompts.find(item => item.id === promptId) || assistantPrompts[0]; const stamp = Date.now();
    setMessages(current => [...current, { id: `user-${stamp}`, role: "user", text: override || prompt.request }, { id: `verified-${stamp}`, role: "assistant", kind: "verified", text: prompt.response, references: prompt.references }, { id: `narration-${stamp}`, role: "assistant", kind: "narration", text: prompt.narration }]);
    setSpecId(prompt.specId); setValue("");
  };
  const send = () => { if (!value.trim()) return; const lower = value.toLowerCase(); const prompt = lower.includes("compare") ? "compare-devices" : lower.includes("chronolog") || lower.includes("timeline") ? "chronology" : lower.includes("correlation") || lower.includes("path") ? "correlation" : lower.includes("summar") ? "summary" : lower.includes("leading") || lower.includes("before") ? "leading-events" : "explain-finding"; runPrompt(prompt, value.trim()); };

  return <div className={`case-assistant-workspace ${compact ? "canvas-compact" : ""}`}>
    <section className="assistant-column">
      <header className="assistant-header"><div className="assistant-orb"><i/></div><div><span className="eyebrow">Central investigation workspace</span><h2>Investigation Assistant</h2><p>Evidence-grounded mock workflow</p></div><span className="ai-status"><i/> Mock ready</span></header>
      <div className="case-context-panel active-investigation-panel"><span className="field-label">Active investigation</span><div><b>{activeCase.reference}</b><strong>{activeCase.name}</strong></div><small>{activeCase.type} case · {activeCase.evidenceCount.toLocaleString()} preserved records</small>{navigate&&<select aria-label="Switch active investigation" value={activeCase.reference} onChange={event=>navigate(`/assistant?case=${event.target.value}`)}>{cases.map(item=><option value={item.reference} key={item.id}>{item.reference} · {item.name}</option>)}</select>}</div>
      <div className="selected-context"><div><span className="field-label">Selected context</span><b>{context.length} references</b></div><div>{context.map(item=><button key={item.id} onClick={() => setContext(current => current.filter(entry => entry.id !== item.id))} title={`Remove ${item.label}`}><small>{item.kind}</small>{item.label}<span>×</span></button>)}</div></div>
      <div className="assistant-thread" aria-live="polite">{messages.map(message=><ConversationMessage key={message.id} message={message}/>)}</div>
      <div className="suggested-prompts"><span className="field-label">Suggested investigations</span><div>{assistantPrompts.map(prompt=><button key={prompt.id} onClick={() => runPrompt(prompt.id)}>{prompt.label}<span>↗</span></button>)}</div></div>
      <div className="assistant-composer"><textarea value={value} onChange={e => setValue(e.target.value)} placeholder="Ask about selected investigation evidence…" aria-label="Assistant message" onKeyDown={e=>{if(e.key === "Enter" && !e.shiftKey){e.preventDefault();send();}}}/><Button variant="primary" onClick={send}>Send ↑</Button><small><span>◇</span> Mock responses only · Grounded in {activeCase.reference} · Verify narration against preserved evidence.</small></div>
    </section>
    <section className="investigation-canvas">
      <header className="canvas-header"><div><span className="eyebrow">Visual investigation</span><h2>{specification.name}</h2><p>{specification.description}</p></div><div className="canvas-meta"><span><b>{specification.evidenceRefs.length}</b> evidence references</span><span className="verified-data"><i/> Rendered from verified investigation data</span></div><div className="canvas-actions"><button className={!compact ? "active" : ""} onClick={() => setCompact(false)} title="Comfortable layout">▦</button><button className={compact ? "active" : ""} onClick={() => setCompact(true)} title="Compact layout">▤</button><Button onClick={() => { setSpecId("incident-context"); setCompact(false); }}>Reset layout</Button></div></header>
      <div className="canvas-spec-bar"><div><span>Validated specification</span><code>{specification.id}</code></div><p>Components and datasets resolve through an allow-listed registry. No executable code is accepted.</p><span>{specification.components.length} panels</span></div>
      <div className="canvas-scroll"><DynamicVisualizationRenderer specification={specification}/></div>
    </section>
  </div>;
}
