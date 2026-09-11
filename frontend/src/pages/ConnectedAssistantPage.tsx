import { useEffect, useRef, useState } from "react";
import { batchApi, type ApiCase } from "../api/batch";
import { normalizeApiError } from "../api/client";
import { phase3Api, type AssistantMessage, type AssistantSession, type ResolvedVisualization, type VisualizationLayout } from "../api/phase3";
import { Button, PageHeader, StatusBadge } from "../components/ui/core";
import { ConnectedVisualizationRenderer } from "../visualizations/ConnectedVisualizationRenderer";

function referencePath(reference: string) { const parts = reference.split(":"); if (parts[0] !== "case" || !/^\d+$/.test(parts[1] ?? "")) return "/cases"; const section = ({ finding: "findings", alert: "alerts", incident: "incidents", timeline: "timeline", evidence: "evidence", event: "events" } as Record<string, string>)[parts[2]] ?? "overview"; return `/cases/${parts[1]}/${section}${parts[3] ? `#${encodeURIComponent(parts.slice(3).join(":"))}` : ""}`; }
function sessionLabel(session: AssistantSession) { if (session.message_count === 0) return "New chat"; const turns = Math.ceil(session.message_count / 2); return `${session.title} · ${turns} turn${turns === 1 ? "" : "s"}`; }

export function ConnectedAssistantPage({ search = window.location.search }: { search?: string }) {
  const params = new URLSearchParams(search); const selectedCase = Number(params.get("case")) || null;
  const selectedReferences = selectedCase ? ["alert", "finding", "evidence", "event", "incident", "timeline"].flatMap(kind => params.get(kind) ? [`case:${selectedCase}:${kind}:${params.get(kind)}`] : []) : [];
  const referenceKey = selectedReferences.join("|");
  const [sessionId, setSessionId] = useState<string | null>(null); const [sessions, setSessions] = useState<AssistantSession[]>([]); const [cases, setCases] = useState<ApiCase[]>([]); const [messages, setMessages] = useState<AssistantMessage[]>([]); const [fallback, setFallback] = useState<ResolvedVisualization | null>(null); const [value, setValue] = useState(""); const [includeEvidence, setIncludeEvidence] = useState(selectedCase !== null || selectedReferences.length > 0); const [state, setState] = useState<"connecting" | "ready" | "thinking" | "offline" | "failed">("connecting"); const [error, setError] = useState<string | null>(null); const [atLatest, setAtLatest] = useState(true); const operation = useRef<AbortController | null>(null); const threadRef = useRef<HTMLDivElement | null>(null); const followLatest = useRef(true);
  useEffect(() => {
    const controller = new AbortController();
    void batchApi.listCases(controller.signal).then(result => setCases(Array.isArray(result?.items) ? result.items : [])).catch(() => { if (!controller.signal.aborted) setCases([]); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController(); const caseIds = selectedCase ? [selectedCase] : []; const storageKey = `traceveil-assistant-${selectedCase ?? "auto"}`;
    const activate = async (session: AssistantSession) => { setSessionId(session.session_id); window.localStorage.setItem(storageKey, session.session_id); const history = await phase3Api.messages(session.session_id, controller.signal); setMessages(Array.isArray(history?.items) ? history.items : []); setState("ready"); };
    void phase3Api.assistantSessions(selectedCase, controller.signal).then(async result => {
      const returned = Array.isArray(result?.items) ? result.items : [];
      const available = referenceKey
        ? returned.filter(item => item.reference_ids.join("|") === referenceKey)
        : selectedCase
          ? returned.filter(item => item.reference_ids.length === 0 && item.case_ids.includes(selectedCase))
          : returned.filter(item => item.case_ids.length === 0 && item.reference_ids.length === 0);
      const requested = params.get("session") ?? window.localStorage.getItem(storageKey);
      const matching = available.find(item => item.session_id === requested);
      const visible = available.filter(item => item.message_count > 0 || item.session_id === requested);
      setSessions(visible);
      if (matching) await activate(matching);
      else if (visible[0]) await activate(visible[0]);
      else { const created = await phase3Api.createAssistantSession(caseIds, selectedReferences, controller.signal); setSessions([created]); await activate(created); }
    }).catch(reason => { if (!controller.signal.aborted) { setState("failed"); setError(normalizeApiError(reason).message); } });
    return () => controller.abort();
  }, [selectedCase, referenceKey]);
  useEffect(() => () => operation.current?.abort(), []);
  useEffect(() => { if (!selectedCase) { setFallback(null); return; } const controller = new AbortController(); void phase3Api.fallbackVisualization(selectedCase, undefined, controller.signal).then(result => setFallback(result?.layout && result?.datasets ? result : null)).catch(() => setFallback(null)); return () => controller.abort(); }, [selectedCase]);
  useEffect(() => {
    if (!followLatest.current && state !== "thinking") return;
    const frame = window.requestAnimationFrame(() => {
      const thread = threadRef.current;
      if (!thread) return;
      thread.scrollTop = thread.scrollHeight;
      setAtLatest(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages.length, state]);
  const scrollToLatest = () => { followLatest.current = true; const thread = threadRef.current; if (thread) thread.scrollTop = thread.scrollHeight; setAtLatest(true); };
  const handleThreadScroll = () => { const thread = threadRef.current; if (!thread) return; const latest = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 48; followLatest.current = latest; setAtLatest(latest); };
  const refresh = async (id: string, signal?: AbortSignal) => { const result = await phase3Api.messages(id, signal); const items = Array.isArray(result?.items) ? result.items : []; setMessages(items); setSessions(current => { const existing = current.find(item => item.session_id === id); if (!existing) return current; const firstQuestion = items.find(item => item.role === "user")?.text.replace(/\s+/g, " ").trim().slice(0, 80); const updated = { ...existing, title: firstQuestion || existing.title, message_count: items.length, updated_at: new Date().toISOString() }; return [updated, ...current.filter(item => item.session_id !== id && item.message_count > 0)]; }); };
  const activateSession = async (id: string) => { operation.current?.abort(); followLatest.current = true; setSessionId(id); setState("connecting"); setError(null); try { await refresh(id); window.localStorage.setItem(`traceveil-assistant-${selectedCase ?? "auto"}`, id); setState("ready"); } catch (reason) { setState("failed"); setError(normalizeApiError(reason).message); } };
  const changeScope = (scope: string) => { window.location.href = scope === "all" ? "/assistant" : `/assistant?case=${encodeURIComponent(scope)}`; };
  const newSession = async () => { operation.current?.abort(); followLatest.current = true; setState("connecting"); setError(null); try { const created = await phase3Api.createAssistantSession(selectedCase ? [selectedCase] : [], selectedReferences); setSessions(items => [created, ...items.filter(item => item.message_count > 0)]); setMessages([]); setSessionId(created.session_id); window.localStorage.setItem(`traceveil-assistant-${selectedCase ?? "auto"}`, created.session_id); setState("ready"); } catch (reason) { setState("failed"); setError(normalizeApiError(reason).message); } };
  const ask = async (question: string, evidenceOverride = includeEvidence) => {
    const normalizedQuestion = question.trim();
    if (!sessionId || !normalizedQuestion || state === "thinking") return;
    const controller = new AbortController(); operation.current = controller; followLatest.current = true; setState("thinking"); setError(null); setValue("");
    try {
      const job = await phase3Api.ask(sessionId, normalizedQuestion, evidenceOverride, controller.signal); await refresh(sessionId, controller.signal);
      const deadline = Date.now() + 130_000;
      for (;;) {
        await new Promise(resolve => window.setTimeout(resolve, 300)); const current = await phase3Api.assistantJob(job.job_id, controller.signal);
        if (current.status === "completed") { await refresh(sessionId, controller.signal); setState("ready"); break; }
        if (current.status === "failed") { setState(current.error?.code === "ollama_offline" ? "offline" : "failed"); setError(current.error?.message ?? "Assistant processing failed."); setValue(normalizedQuestion); break; }
        if (Date.now() >= deadline) throw new Error("Assistant processing timed out. You can safely retry.");
      }
    } catch (reason) { if (!controller.signal.aborted) { setState("failed"); setError(normalizeApiError(reason).message); setValue(normalizedQuestion); } }
  };
  const latestLayout = messages.reduce<VisualizationLayout | null>((layout, message) => message.visualization ?? layout, null);
  const stateLabel = { connecting: "Connecting", ready: "Ready", thinking: "Working", offline: "Ollama offline", failed: "Unavailable" }[state];
  const messageKind = (message: AssistantMessage) => message.model === "deterministic-greeting" ? "Instant greeting" : message.model === "deterministic-conversation" ? "Local fallback" : message.model === "deterministic-fallback" ? "Deterministic fallback" : `AI narration · ${message.model ?? "local model"}`;
  const suggestedQuestions = [
    { label: "Highest-risk finding", question: "Summarize the highest-risk finding" },
    { label: "Latest live alert", question: "Explain the latest live alert" },
    { label: "Forensic timeline", question: "Show the forensic timeline" },
  ];
  return <><PageHeader eyebrow="Grounded local assistance · Connected API" title="Traceveil Assistant" description="Narration is generated from bounded persisted context; deterministic findings remain authoritative." actions={<StatusBadge status={stateLabel}/>} />
    <div className="case-assistant-workspace global-assistant-workspace connected-assistant-workspace"><section className="assistant-column global-assistant-column"><header className="assistant-header"><div className="assistant-orb"><i/></div><div><span className="eyebrow">Grounded investigation assistant</span><h2>Investigation chat</h2><p>{selectedCase ? `Scoped to persisted case ${selectedCase}` : "Auto retrieval across persisted cases"}</p></div><span className={`ai-status ai-status-${state}`}><i/> {stateLabel}</span></header>
      <div className="assistant-scope-panel"><div><span className="field-label">Investigation scope</span><select aria-label="Investigation scope" value={selectedCase?.toString() ?? "all"} onChange={event => changeScope(event.target.value)}><option value="all">All persisted cases</option>{selectedCase && !cases.some(item => item.id === selectedCase) && <option value={selectedCase}>Case {selectedCase}</option>}{cases.map(item => <option value={item.id} key={item.id}>Case {item.id} · {item.name}</option>)}</select></div><div><span className="field-label">Chat history</span><select aria-label="Chat history" value={sessionId ?? ""} onChange={event => void activateSession(event.target.value)}><option value="" disabled>Select chat</option>{sessions.map(session => <option value={session.session_id} key={session.session_id}>{sessionLabel(session)}</option>)}</select></div><Button variant="secondary" onClick={() => void newSession()}>＋ New chat</Button></div>
      {selectedReferences.length > 0 && <div className="selected-context"><div><span className="field-label">Selected persisted context</span><b>{selectedReferences.length} selected reference{selectedReferences.length === 1 ? "" : "s"} · Retrieval locked</b></div><div>{selectedReferences.map(reference => <button key={reference} onClick={() => { window.location.href = referencePath(reference); }}><small>{reference.split(":")[2]}</small>{reference.split(":").slice(3).join(":")}<span>↗</span></button>)}</div></div>}
      {error && <div className="state-box" role="alert"><strong>{state === "offline" ? "Ollama is optional and offline" : "Assistant unavailable"}</strong><p>{error}</p></div>}
      <div className="assistant-thread" ref={threadRef} onScroll={handleThreadScroll} aria-label="Conversation messages" aria-live="polite" aria-busy={state === "thinking"} tabIndex={0}>{messages.length ? messages.map(message => <article className={`assistant-message assistant-message-${message.role}`} key={message.message_id}><div className="message-avatar">{message.role === "assistant" ? "TV" : "IN"}</div><div className="message-content"><div className="message-byline"><b>{message.role === "assistant" ? "Traceveil Assistant" : "Investigator"}</b>{message.role === "assistant" && <span className={`message-kind ${message.model?.startsWith("deterministic-") ? "kind-verified" : "kind-narration"}`}>{messageKind(message)}</span>}</div><p>{message.text}</p>{message.citations.length > 0 && <div className="assistant-references" aria-label="Verified persisted facts"><strong>Verified persisted sources</strong>{message.citations.map(reference => <a className="evidence-reference" href={referencePath(reference)} key={reference}>{reference}<span>↗</span></a>)}</div>}{message.caveats.map(caveat => <small className="assistant-caveat" key={caveat}>{caveat}</small>)}</div></article>) : <div className="state-box assistant-empty-state"><strong>Start with a question—or just say hello</strong><p>Turn on investigation evidence when you want answers grounded in persisted cases.</p></div>}{state === "thinking" && <div className="assistant-message assistant-thinking"><div className="message-avatar">TV</div><div className="message-content"><div className="message-byline"><b>Traceveil Assistant</b><span className="message-kind kind-narration">Working</span></div><p>{includeEvidence ? "Retrieving and validating grounded context…" : "Generating a response…"}</p></div></div>}</div>
      {!atLatest && <button className="assistant-jump-latest" onClick={scrollToLatest}>↓ Jump to latest</button>}
      <div className="suggested-prompts"><span className="field-label">Try asking</span><div>{suggestedQuestions.map(item => <button key={item.question} disabled={state === "thinking" || !sessionId} onClick={() => { setIncludeEvidence(true); void ask(item.question, true); }}>{item.label}<span>↗</span></button>)}</div></div>
      <div className="assistant-composer"><textarea value={value} maxLength={4000} disabled={!sessionId || state === "thinking"} onChange={event => setValue(event.target.value)} placeholder={sessionId ? includeEvidence ? "Ask about persisted investigation evidence…" : "Message Traceveil Assistant…" : "Preparing a conversation…"} aria-label="Assistant message" onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ask(value); } }}/>{state === "thinking" ? <Button variant="secondary" onClick={() => { operation.current?.abort(); setState("ready"); }}>Stop waiting</Button> : <Button variant="primary" disabled={!sessionId || !value.trim()} onClick={() => void ask(value)}>Ask ↑</Button>}<label className="assistant-evidence-toggle"><input type="checkbox" checked={includeEvidence} disabled={state === "thinking"} onChange={event => setIncludeEvidence(event.target.checked)}/><span><b>Include investigation evidence</b><small>{includeEvidence ? "Ground answers in the selected persisted scope" : "Normal chat without case retrieval"}</small></span></label><small className="assistant-composer-hint"><span>◇</span> Enter to send · Shift+Enter for a new line · {value.length.toLocaleString("en-US")}/4,000</small></div></section>
      <section className="investigation-canvas"><header className="canvas-header"><div><span className="eyebrow">Safe visualization boundary</span><h2>{latestLayout?.title ?? fallback?.layout?.title ?? "Validated investigation overview"}</h2><p>Only allow-listed layouts and backend-resolved values are rendered.</p></div><div className="canvas-meta"><span><b>{latestLayout?.components.length ?? fallback?.layout?.components.length ?? 0}</b> validated components</span><span className="verified-data"><i/> Persisted deterministic data</span></div></header><div className="canvas-scroll">{latestLayout || fallback?.layout ? <ConnectedVisualizationRenderer layout={latestLayout} initial={latestLayout ? null : fallback}/> : <div className="state-box"><strong>Select a case to visualize</strong><p>A deterministic overview appears without requiring Qwen.</p></div>}</div></section></div></>;
}
