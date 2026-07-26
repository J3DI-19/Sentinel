import { AppShell, useLocationPath } from "../layouts/RefinedAppShell";
import { OverviewCommandCenter } from "../pages/OverviewCommandCenter";
import { CasesPage } from "../pages/CasesPage";
import { LiveOperationsPage } from "../pages/LiveOperationsPage";
import { ImportEvidencePage } from "../pages/ImportEvidencePage";
import { SystemStatusPage } from "../pages/SystemStatusPage";
import { SettingsWorkspacePage } from "../pages/SettingsWorkspacePage";
import { CaseWorkspacePage } from "../pages/CaseWorkspacePage";
import { GlobalInvestigationAssistantPage } from "../pages/GlobalInvestigationAssistantPage";

export function Router() {
  const route=useLocationPath(); let page;
  if(route.path==="/") page=<OverviewCommandCenter navigate={route.navigate}/>;
  else if(route.path==="/assistant") page=<GlobalInvestigationAssistantPage search={route.search}/>;
  else if(route.path==="/cases") page=<CasesPage navigate={route.navigate}/>;
  else if(route.path.startsWith("/cases/")) page=<CaseWorkspacePage path={route.path} navigate={route.navigate}/>;
  else if(route.path==="/live") page=<LiveOperationsPage navigate={route.navigate}/>;
  else if(route.path==="/import") page=<ImportEvidencePage/>;
  else if(route.path==="/status") page=<SystemStatusPage/>;
  else if(route.path==="/settings") page=<SettingsWorkspacePage/>;
  else page=<div className="not-found"><span>404</span><h1>Investigation view not found</h1><button onClick={()=>route.navigate("/")}>Return to overview</button></div>;
  return <AppShell route={route}>{page}</AppShell>;
}
