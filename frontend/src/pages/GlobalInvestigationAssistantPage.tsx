import { GlobalAssistantWorkspace, type PinnedAssistantReference } from "../features/assistant/GlobalAssistantWorkspace";
import { cases } from "../mocks/data";

export function GlobalInvestigationAssistantPage({ search = window.location.search }: { search?: string }) {
  const params = new URLSearchParams(search);
  const pins: PinnedAssistantReference[] = [];
  const caseValue = params.get("case");
  if (caseValue) { const item = cases.find(entry=>entry.reference===caseValue||entry.id===caseValue); pins.push({ id:item?.reference||caseValue, label:item?.reference||caseValue, kind:"Case" }); }
  for (const [key, kind] of [["finding","Finding"],["alert","Alert"],["evidence","Evidence"],["device","Device"]] as const) { const value=params.get(key); if(value) pins.push({id:value,label:value,kind}); }
  return <GlobalAssistantWorkspace key={pins.map(pin=>pin.id).join("-")||"auto"} initialPins={pins}/>;
}
