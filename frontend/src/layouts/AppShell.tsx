import { useEffect, useState, type ReactNode } from "react";
import { cases } from "../mocks/data";

export interface RouteState { path: string; navigate: (path: string) => void; }
const nav = [
  { path: "/", label: "Overview", icon: "▦" }, { path: "/cases", label: "Cases", icon: "□" },
  { path: "/live", label: "Live Monitor", icon: "◉" }, { path: "/import", label: "Import Evidence", icon: "⇧" },
  { path: "/status", label: "System Status", icon: "⌁" }, { path: "/settings", label: "Settings", icon: "⚙" },
];
export function useLocationPath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(()=>{ const fn=()=>setPath(window.location.pathname); window.addEventListener("popstate",fn); return()=>window.removeEventListener("popstate",fn); },[]);
  const navigate=(next:string)=>{window.history.pushState({},"",next);setPath(next);window.scrollTo({top:0,behavior:"smooth"});};
  return {path,navigate};
}
function crumbLabel(path: string) {
  const parts=path.split("/").filter(Boolean); if(!parts.length)return ["Overview"];
  return parts.map((p,i)=> i===1 && parts[0]==="cases" ? cases.find(c=>c.id===p)?.name || p : p.charAt(0).toUpperCase()+p.slice(1));
}
export function AppShell({ children, route }: { children: ReactNode; route: RouteState }) {
  const [collapsed,setCollapsed]=useState(false); const [mobile,setMobile]=useState(false); const crumbs=crumbLabel(route.path);
  const activeFor=(path:string)=>path==="/"?route.path==="/":route.path.startsWith(path);
  return <div className={`app-shell ${collapsed?"sidebar-collapsed":""}`}><aside className={`sidebar ${mobile?"mobile-open":""}`}><div className="brand" onClick={()=>route.navigate("/")}><div className="brand-mark">T</div><div><strong>Traceveil</strong><span>IoT DFIR Platform</span></div></div><div className="nav-label">Command center</div><nav>{nav.slice(0,4).map(item=><button key={item.path} className={activeFor(item.path)?"active":""} onClick={()=>{route.navigate(item.path);setMobile(false)}}><span>{item.icon}</span><b>{item.label}</b>{item.path==="/live"&&<i/>}</button>)}</nav><div className="nav-label">Platform</div><nav>{nav.slice(4).map(item=><button key={item.path} className={activeFor(item.path)?"active":""} onClick={()=>{route.navigate(item.path);setMobile(false)}}><span>{item.icon}</span><b>{item.label}</b></button>)}</nav><div className="sidebar-foot"><div className="collector-mini"><i/><div><b>Collector active</b><span>Mock stream · 86 ev/min</span></div></div><button className="collapse-button" onClick={()=>setCollapsed(!collapsed)}>{collapsed?"›":"‹"}</button><div className="profile"><span>IN</span><div><b>Investigator</b><small>Local Workspace</small></div><button>···</button></div></div></aside><div className="app-main"><header className="topbar"><button className="mobile-menu" onClick={()=>setMobile(!mobile)}>☰</button><div className="breadcrumbs"><button onClick={()=>route.navigate("/")}>Traceveil</button>{crumbs.map((c,i)=><span key={c}>› <b>{c}</b></span>)}</div><div className="top-actions"><div className="global-search">⌕ <input placeholder="Search evidence, devices, cases…" aria-label="Global search"/><kbd>⌘ K</kbd></div><button className="icon-button" aria-label="Notifications">♢<i/></button><div className="api-status"><i/><span>API connected</span></div></div></header><main className="content">{children}</main></div>{mobile&&<button className="mobile-backdrop" onClick={()=>setMobile(false)} aria-label="Close navigation"/>}</div>;
}
