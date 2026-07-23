import { useState } from "react";
import { Button } from "../../components/ui/core";
import { cases } from "../../mocks/data";
import { assistantPrompts, visualizationSpecs, type AssistantMessageData } from "../../mocks/assistant";
import { DynamicVisualizationRenderer } from "../../visualizations/DynamicVisualizationRenderer";

export interface PinnedAssistantReference { id: string; label: string; kind: string; }
type Scope = "Auto" | "All cases" | "Specific case" | "Selected references";

function ReferenceChip({ reference }: { reference: string }) { return <button className="evidence-reference" title={`Retrieved source ${reference}`}>{reference}<span>↗</span></button>; }
function Message({ message }: { message: AssistantMessageData }) {
  const assistant = message.role === "assistant";
  return <article className={`assistant-message assistant-message-${message.role}`}><div className="message-avatar">{assistant ? "TV" : "IN"}</div><div className="message-content"><div className="message-byline"><b>{assistant ? "Traceveil Assistant" : "Investigator"}</b>{assistant&&<span className={`message-kind kind-${message.kind}`}>{message.kind === "verified" ? "✓ Verified facts" : "AI narration"}</span>}</div><p>{message.text}</p>{message.references&&<div className="assistant-references">{message.references.map(reference=><ReferenceChip key={reference} reference={reference}/>)}</div>}</div></article>;
}

const welcome: AssistantMessageData[] = [{ id: "global-welcome", role: "assistant", kind: "narration", text: "Ask naturally across Traceveil. I’ll retrieve relevant mock cases, evidence, alerts, findings, and devices, then keep verified facts separate from explanatory narration." }];
const globalSuggestions = ["Summarize what happened on 17 July", "Show suspicious camera activity", "What are the highest-risk unresolved findings?"];

export function GlobalAssistantWorkspace({ initialPins = [] }: { initialPins?: PinnedAssistantReference[] }) {
  const [scope, setScope] = useState<Scope>("Auto");
  const [specificCase, setSpecificCase] = useState(cases[0].reference);
  const [pins, setPins] = useState(initialPins);
  const [messages, setMessages] = useState<AssistantMessageData[]>(welcome);
  const [sources, setSources] = useState(initialPins.map(item=>item.id));
  const [specId, setSpecId] = useState("global-overview");
  const [value, setValue] = useState("");
  const [compact, setCompact] = useState(false);
  const specification = visualizationSpecs[specId] || visualizationSpecs["global-overview"];

  function selectPrompt(question: string) {
    const lower = question.toLowerCase();
    if (lower.includes("17 july") || lower.includes("july 17") || lower.includes("17th")) return "global-date";
    if (lower.includes("camera")) return "global-camera";
    if ((lower.includes("highest") || lower.includes("risk")) && (lower.includes("finding") || lower.includes("unresolved"))) return "global-risk";
    if (lower.includes("compare")) return "compare-devices";
    if (lower.includes("chronolog") || lower.includes("timeline")) return "chronology";
    if (lower.includes("correlation") || lower.includes("path")) return "correlation";
    if (lower.includes("leading") || lower.includes("before")) return "leading-events";
    if (lower.includes("summar")) return pins.length ? "summary" : "global-date";
    return pins.some(pin=>pin.kind === "Finding") ? "explain-finding" : "global-risk";
  }

  function ask(question: string) {
    if (!question.trim()) return;
    const prompt = assistantPrompts.find(item=>item.id === selectPrompt(question)) || assistantPrompts[0];
    const stamp = Date.now();
    setMessages(current=>[...current,
      { id:`user-${stamp}`, role:"user", text:question.trim() },
      { id:`verified-${stamp}`, role:"assistant", kind:"verified", text:prompt.response, references:prompt.references },
      { id:`narration-${stamp}`, role:"assistant", kind:"narration", text:prompt.narration },
    ]);
    setSources(prompt.references);
    setSpecId(prompt.specId);
    setValue("");
  }

  function updateScope(next: Scope) {
    setScope(next);
    if (next === "Selected references" && !pins.length) setScope("Auto");
  }

  return <div className={`case-assistant-workspace global-assistant-workspace ${compact?"canvas-compact":""}`}>
    <section className="assistant-column global-assistant-column">
      <header className="assistant-header"><div className="assistant-orb"><i/></div><div><span className="eyebrow">Global forensic intelligence</span><h2>Traceveil Assistant</h2><p>Ask naturally · retrieve verified context</p></div><span className="ai-status"><i/> Mock ready</span></header>
      <div className="assistant-scope-panel">
        <div><span className="field-label">Investigation scope</span><b>Retrieval decides what is relevant</b></div>
        <select aria-label="Assistant scope" value={scope} onChange={event=>updateScope(event.target.value as Scope)}><option>Auto</option><option>All cases</option><option>Specific case</option><option disabled={!pins.length}>Selected references</option></select>
        {scope === "Specific case"&&<select aria-label="Specific case" value={specificCase} onChange={event=>setSpecificCase(event.target.value)}>{cases.map(item=><option key={item.id} value={item.reference}>{item.reference} · {item.name}</option>)}</select>}
      </div>
      <div className="selected-context global-pins"><div><span className="field-label">Pinned context · Optional</span><b>{pins.length} pinned</b></div><div>{pins.length?pins.map(item=><button key={`${item.kind}-${item.id}`} onClick={()=>setPins(current=>current.filter(pin=>pin!==item))} title={`Remove ${item.label}`}><small>{item.kind}</small>{item.label}<span>×</span></button>):<p>Contextual links appear here. Auto retrieval works without pins.</p>}</div></div>
      <div className="assistant-thread" aria-live="polite">{messages.map(message=><Message key={message.id} message={message}/>)}</div>
      <div className="retrieved-context"><div><span className="field-label">Retrieved context · Sources used</span><b>{sources.length} sources</b></div>{sources.length?<div>{sources.map(source=><ReferenceChip key={source} reference={source}/>)}</div>:<p>Sources will appear after Traceveil retrieves context for your question.</p>}</div>
      <div className="suggested-prompts"><span className="field-label">Try asking</span><div>{globalSuggestions.map(question=><button key={question} onClick={()=>ask(question)}>{question}<span>↗</span></button>)}</div></div>
      <div className="assistant-composer"><textarea value={value} onChange={event=>setValue(event.target.value)} placeholder="Ask Traceveil anything…" aria-label="Assistant message" onKeyDown={event=>{if(event.key==="Enter"&&!event.shiftKey){event.preventDefault();ask(value)}}}/><Button variant="primary" onClick={()=>ask(value)}>Ask ↑</Button><small><span>◇</span> Mock retrieval and responses only · Verify AI narration against cited sources.</small></div>
    </section>
    <section className="investigation-canvas">
      <header className="canvas-header"><div><span className="eyebrow">Dynamic visual investigation</span><h2>{specification.name}</h2><p>{specification.description}</p></div><div className="canvas-meta"><span><b>{specification.evidenceRefs.length}</b> verified references</span><span className="verified-data"><i/> Rendered from verified investigation data</span></div><div className="canvas-actions"><button className={!compact?"active":""} onClick={()=>setCompact(false)} title="Comfortable layout">▦</button><button className={compact?"active":""} onClick={()=>setCompact(true)} title="Compact layout">▤</button><Button onClick={()=>{setSpecId("global-overview");setCompact(false)}}>Reset view</Button></div></header>
      <div className="canvas-spec-bar"><div><span>Validated specification</span><code>{specification.id}</code></div><p>Traceveil selects allow-listed components and deterministic data references. No generated code or raw numerical arrays are executed.</p><span>{specification.components.length} panels</span></div>
      <div className="canvas-scroll"><DynamicVisualizationRenderer specification={specification}/></div>
    </section>
  </div>;
}
