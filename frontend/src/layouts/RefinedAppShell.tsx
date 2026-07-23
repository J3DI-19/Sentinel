import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cases, devices, evidence, findings } from "../mocks/data";

export interface RouteState { path: string; navigate: (path: string) => void; }

const workspaceNav = [
  { path: "/", label: "Overview", icon: "▦" },
  { path: "/assistant", label: "Investigation Assistant", icon: "◎" },
  { path: "/cases", label: "Cases", icon: "□" },
  { path: "/live", label: "Live Monitor", icon: "◉" },
  { path: "/import", label: "Import Evidence", icon: "⇧" },
];
const platformNav = [{ path: "/status", label: "System Status", icon: "⌁" }, { path: "/settings", label: "Settings", icon: "⚙" }];

export function useLocationPath() {
  const [location, setLocation] = useState(() => ({ path: window.location.pathname, search: window.location.search }));
  useEffect(() => { const update = () => setLocation({ path: window.location.pathname, search: window.location.search }); window.addEventListener("popstate", update); return () => window.removeEventListener("popstate", update); }, []);
  const navigate = (next: string) => { const target = new URL(next, window.location.origin); window.history.pushState({}, "", next); setLocation({ path: target.pathname, search: target.search }); if (!navigator.userAgent.includes("jsdom")) window.scrollTo({ top: 0, behavior: "smooth" }); };
  return { path: location.path, navigate };
}

function Breadcrumbs({ path, navigate }: { path: string; navigate: (path: string) => void }) {
  const parts = path.split("/").filter(Boolean);
  if (parts[0] === "cases" && parts[1]) {
    const item = cases.find(entry => entry.id === parts[1]);
    const section = parts[2] ? parts[2].charAt(0).toUpperCase() + parts[2].slice(1) : "Overview";
    return <div className="breadcrumbs"><button onClick={() => navigate("/cases")}>Cases</button><span>/</span><button onClick={() => navigate(`/cases/${parts[1]}/overview`)}>{item?.reference || parts[1]}</button><span>/</span><b>{section}</b></div>;
  }
  const labels: Record<string, string> = { "/": "Overview", "/assistant": "Investigation Assistant", "/cases": "Cases", "/live": "Live Monitor", "/import": "Import Evidence", "/status": "System Status", "/settings": "Settings" };
  return <div className="breadcrumbs breadcrumbs-single"><b>{labels[path] || "Traceveil"}</b></div>;
}

export function AppShell({ children, route }: { children: ReactNode; route: RouteState }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const activeFor = (path: string) => path === "/" ? route.path === "/" : route.path.startsWith(path);
  const targets = useMemo(() => [
    { label: "Investigation Assistant", detail: "Central evidence-grounded workspace", path: "/assistant", kind: "Workspace" },
    { label: "Cases", detail: "Investigation register", path: "/cases", kind: "Workspace" },
    { label: "Live Monitor", detail: "Current controlled activity", path: "/live", kind: "Workspace" },
    { label: "Import Evidence", detail: "Historical and batch evidence", path: "/import", kind: "Workspace" },
    { label: "System Status", detail: "Platform health", path: "/status", kind: "Platform" },
    ...cases.map(item => ({ label: item.name, detail: item.reference, path: `/cases/${item.id}/overview`, kind: "Case" })),
    ...evidence.map(item => ({ label: item.id, detail: `${item.device} · ${item.eventType}`, path: `/assistant?case=${cases[0].reference}&evidence=${item.id}`, kind: "Evidence" })),
    ...findings.map(item => ({ label: item.id, detail: item.title, path: `/assistant?case=${cases[0].reference}&finding=${item.id}`, kind: "Finding" })),
    ...devices.map(item => ({ label: item.name, detail: item.ip, path: `/assistant?case=${cases[0].reference}&device=${item.id}`, kind: "Device" })),
  ], []);
  const results = targets.filter(item => `${item.label} ${item.detail} ${item.kind}`.toLowerCase().includes(search.toLowerCase())).slice(0, 7);
  const selectTarget = (path: string) => { route.navigate(path); setSearch(""); setSearchOpen(false); };

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); searchRef.current?.focus(); }
      if (event.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", shortcut); return () => window.removeEventListener("keydown", shortcut);
  }, []);

  const renderNav = (items: typeof workspaceNav) => <nav>{items.map(item => <button key={item.path} title={collapsed ? item.label : undefined} aria-label={item.label} className={activeFor(item.path) ? "active" : ""} onClick={() => { route.navigate(item.path); setMobile(false); }}><span>{item.icon}</span><b>{item.label}</b></button>)}</nav>;

  return <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
    <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
      <button className="brand" onClick={() => route.navigate("/")} aria-label="Traceveil overview"><span className="brand-mark">T</span><span className="brand-copy"><strong>Traceveil</strong><small>IoT DFIR Platform</small></span></button>
      <div className="nav-label">Workspace</div>{renderNav(workspaceNav)}
      <div className="nav-label">Platform</div>{renderNav(platformNav)}
      <div className="sidebar-collapse-area"><button className="collapse-button" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} title={collapsed ? "Expand sidebar" : "Collapse sidebar"}>{collapsed ? "›" : "‹"}</button></div>
    </aside>
    <div className="app-main">
      <header className="topbar">
        <button className="mobile-menu" onClick={() => setMobile(!mobile)} aria-label="Open navigation">☰</button>
        <Breadcrumbs path={route.path} navigate={route.navigate}/>
        <div className="top-actions">
          <div className={`global-search ${searchOpen ? "open" : ""}`}>
            <span>⌕</span><input ref={searchRef} value={search} onFocus={() => setSearchOpen(true)} onChange={event => { setSearch(event.target.value); setSearchOpen(true); }} placeholder="Search cases, evidence, devices…" aria-label="Global search"/><kbd>Ctrl/⌘ K</kbd>
            {searchOpen && <div className="command-results" role="listbox">{results.length ? results.map(item => <button role="option" aria-selected="false" key={`${item.kind}-${item.label}`} onMouseDown={event => event.preventDefault()} onClick={() => selectTarget(item.path)}><span><b>{item.label}</b><small>{item.detail}</small></span><em>{item.kind}</em></button>) : <div className="command-empty">No matching cases, evidence, devices, or findings.</div>}</div>}
          </div>
          <button className="health-indicator" onClick={() => route.navigate("/status")} aria-label="Platform health: healthy" title="Platform healthy · View system status"><i/></button>
        </div>
      </header>
      <main className="content" onClick={() => searchOpen && setSearchOpen(false)}>{children}</main>
    </div>
    {mobile && <button className="mobile-backdrop" onClick={() => setMobile(false)} aria-label="Close navigation"/>}
  </div>;
}
