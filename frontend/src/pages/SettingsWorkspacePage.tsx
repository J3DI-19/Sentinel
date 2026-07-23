import { useState, type ReactNode } from "react";
import { Button, PageHeader, StatusBadge } from "../components/ui/core";

type Tab = "Preferences" | "Model settings" | "Alert rules" | "Email delivery";
type ToggleProps = { label: string; description: string; checked: boolean; onChange: (value: boolean) => void; disabled?: boolean };

const tabs: Array<{ name: Tab; description: string; status: string; icon: string }> = [
  { name: "Preferences", description: "Interface and investigation defaults", status: "Local", icon: "◫" },
  { name: "Model settings", description: "Optional AI runtime configuration", status: "Mock only", icon: "✦" },
  { name: "Alert rules", description: "Default triage and escalation behavior", status: "Mock only", icon: "◇" },
  { name: "Email delivery", description: "Report and alert notification defaults", status: "Unavailable", icon: "↗" },
];

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <section className="settings-section"><header><h3>{title}</h3><p>{description}</p></header>{children}</section>;
}

function Toggle({ label, description, checked, onChange, disabled }: ToggleProps) {
  return <div className={`setting-row ${disabled ? "is-disabled" : ""}`}><div><b>{label}</b><p>{description}</p></div><label className="switch"><input aria-label={label} type="checkbox" checked={checked} disabled={disabled} onChange={event => onChange(event.target.checked)}/><i/></label></div>;
}

function SelectField({ label, description, value, onChange, children, disabled }: { label: string; description: string; value: string; onChange: (value: string) => void; children: ReactNode; disabled?: boolean }) {
  return <label className={`setting-control ${disabled ? "is-disabled" : ""}`}><span><b>{label}</b><small>{description}</small></span><select aria-label={label} value={value} onChange={event => onChange(event.target.value)} disabled={disabled}>{children}</select></label>;
}

export function SettingsWorkspacePage() {
  const [tab, setTab] = useState<Tab>("Preferences");
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  const [preferences, setPreferences] = useState({ compact: false, motion: false, clock: true, timezone: "Asia/Kolkata", start: "Overview" });
  const [model, setModel] = useState({ enabled: false, references: true, provider: "Local Ollama", name: "llama3.2:3b" });
  const [alerts, setAlerts] = useState({ critical: true, high: true, medium: false, threshold: "80", window: "15 minutes" });
  const current = tabs.find(item => item.name === tab)!;
  const change = (action: () => void) => { action(); setDirty(true); setSaved(false); };
  const toggle = (label: string, description: string, checked: boolean, action: (value: boolean) => void, disabled = false) => <Toggle label={label} description={description} checked={checked} onChange={value => change(() => action(value))} disabled={disabled}/>;

  return <>
    <PageHeader eyebrow="Workspace configuration" title="Settings" description="Configure local investigation preferences and review the boundaries of planned platform integrations." actions={<span className="settings-scope"><i/>This browser session</span>}/>
    <div className="settings-notice" role="note"><span>i</span><div><b>Frontend settings preview</b><p>Changes affect this interface session only. No account service, secrets store, alert engine, or delivery service is connected.</p></div></div>
    <div className="settings-layout">
      <aside className="settings-nav" aria-label="Settings sections">
        <div className="settings-nav-label">Configuration</div>
        {tabs.map(item => <button key={item.name} className={tab === item.name ? "active" : ""} aria-current={tab === item.name ? "page" : undefined} onClick={() => { setTab(item.name); setSaved(false); }}><span className="settings-nav-icon">{item.icon}</span><span><b>{item.name}</b><small>{item.description}</small></span><em>›</em></button>)}
        <div className="settings-nav-foot"><b>Configuration state</b><span><i/>Mock-backed interface</span></div>
      </aside>
      <main className="settings-panel panel">
        <header className="settings-panel-head"><div><span className="eyebrow">Configuration section</span><h2>{current.name}</h2><p>{current.description}</p></div><StatusBadge status={current.status}/></header>

        {tab === "Preferences" && <>
          <Section title="Interface behavior" description="Choose how investigation data is presented in this browser.">
            {toggle("Compact evidence rows", "Show more evidence records within the same viewport.", preferences.compact, value => setPreferences({ ...preferences, compact: value }))}
            {toggle("Reduce motion", "Limit animated graph edges and non-essential interface transitions.", preferences.motion, value => setPreferences({ ...preferences, motion: value }))}
            {toggle("24-hour timestamps", "Display forensic timestamps using the 24-hour clock.", preferences.clock, value => setPreferences({ ...preferences, clock: value }))}
          </Section>
          <Section title="Investigation defaults" description="Set the initial context used when entering the workspace."><div className="settings-control-grid">
            <SelectField label="Default timezone" description="Used for evidence and timeline timestamps." value={preferences.timezone} onChange={value => change(() => setPreferences({ ...preferences, timezone: value }))}><option value="Asia/Kolkata">Asia/Kolkata (UTC+05:30)</option><option value="UTC">UTC</option><option value="America/New_York">America/New_York</option><option value="Europe/London">Europe/London</option></SelectField>
            <SelectField label="Start page" description="First workspace shown after sign-in." value={preferences.start} onChange={value => change(() => setPreferences({ ...preferences, start: value }))}><option>Overview</option><option>Cases</option><option>Live Monitor</option><option>System Status</option></SelectField>
          </div></Section>
        </>}

        {tab === "Model settings" && <>
          <Section title="Optional AI runtime" description="Keep generated narrative separate from verified investigation evidence.">
            <div className="settings-runtime-card"><span>AI</span><div><b>Local model runtime</b><p>Optional service · currently disconnected</p></div><StatusBadge status="Optional offline"/></div>
            {toggle("Enable AI-assisted narrative", "Generate clearly labeled summaries from selected evidence.", model.enabled, value => setModel({ ...model, enabled: value }))}
            {toggle("Require evidence references", "Retain links to supporting mock records in generated responses.", model.references, value => setModel({ ...model, references: value }))}
          </Section>
          <Section title="Runtime connection" description="Illustrative fields; values are not sent outside this browser."><div className="settings-control-grid">
            <SelectField label="Provider" description="Planned local inference provider." value={model.provider} onChange={value => change(() => setModel({ ...model, provider: value }))}><option>Local Ollama</option></SelectField>
            <SelectField label="Model" description="Planned model identifier." value={model.name} onChange={value => change(() => setModel({ ...model, name: value }))}><option>llama3.2:3b</option><option>qwen2.5:7b</option></SelectField>
          </div><label className="setting-control setting-control-full"><span><b>Endpoint</b><small>Local-only placeholder; connectivity is not tested here.</small></span><input aria-label="Endpoint" value="http://127.0.0.1:11434" readOnly/></label></Section>
        </>}

        {tab === "Alert rules" && <>
          <Section title="Default alert intake" description="Choose which future detections should enter the investigation queue.">
            {toggle("Critical detections", "Surface critical detections immediately.", alerts.critical, value => setAlerts({ ...alerts, critical: value }))}
            {toggle("High-severity detections", "Surface high-severity detections for review.", alerts.high, value => setAlerts({ ...alerts, high: value }))}
            {toggle("Medium-severity detections", "Include medium-severity detections by default.", alerts.medium, value => setAlerts({ ...alerts, medium: value }))}
          </Section>
          <Section title="Triage defaults" description="Mock thresholds used to preview intended alert behavior."><div className="settings-control-grid">
            <SelectField label="Escalation threshold" description="Minimum score for escalation." value={alerts.threshold} onChange={value => change(() => setAlerts({ ...alerts, threshold: value }))}><option value="70">70 risk</option><option value="80">80 risk</option><option value="90">90 risk</option></SelectField>
            <SelectField label="Grouping window" description="Combine related detections." value={alerts.window} onChange={value => change(() => setAlerts({ ...alerts, window: value }))}><option>5 minutes</option><option>15 minutes</option><option>30 minutes</option></SelectField>
          </div></Section>
        </>}

        {tab === "Email delivery" && <>
          <div className="settings-unavailable"><span>↗</span><div><b>Delivery service unavailable</b><p>Traceveil does not currently send email. These controls preview the intended notification policy only.</p></div></div>
          <Section title="Notification defaults" description="Requires a future authenticated delivery service.">
            {toggle("Approved report delivery", "Email a report after investigator approval and sign-off.", false, () => undefined, true)}
            {toggle("Critical alert notification", "Notify the owner when a critical alert is created.", false, () => undefined, true)}
            <div className="settings-control-grid"><label className="setting-control is-disabled"><span><b>Default recipient</b><small>Requires user and case ownership data.</small></span><input aria-label="Default recipient" value="investigator@traceveil.local" readOnly disabled/></label><SelectField label="Digest frequency" description="Scheduled investigation summaries." value="Never" onChange={() => undefined} disabled><option>Never</option></SelectField></div>
          </Section>
        </>}

        <footer className="settings-save"><span className={saved ? "settings-saved" : ""}>{saved ? "✓ Settings applied to this browser session." : dirty ? "Unsaved session changes" : "No unsaved changes"}</span><Button variant="primary" disabled={!dirty || tab === "Email delivery"} onClick={() => { setDirty(false); setSaved(true); }}>Save {tab.toLowerCase()}</Button></footer>
      </main>
    </div>
  </>;
}
