import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getSystemStatus, type ServiceStatus } from "../api/health";

export type CoreHealthState = "checking" | "operational" | "database-unavailable" | "backend-unavailable";

interface SystemHealthValue {
  services: ServiceStatus[];
  state: CoreHealthState;
  checked: string;
  loading: boolean;
  refresh: () => Promise<void>;
}

const SystemHealthContext = createContext<SystemHealthValue | null>(null);

function coreState(services: ServiceStatus[], loading: boolean): CoreHealthState {
  if (loading) return "checking";
  const api = services.find(service => service.service === "api");
  if (api?.status !== "ok") return "backend-unavailable";
  const database = services.find(service => service.service === "database");
  return database?.status === "ok" ? "operational" : "database-unavailable";
}

export function SystemHealthProvider({ children }: { children: ReactNode }) {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [checked, setChecked] = useState("Not checked");
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setServices(await getSystemStatus());
      setChecked("Just now");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  const value = useMemo(() => ({ services, state: coreState(services, loading), checked, loading, refresh }), [checked, loading, refresh, services]);
  return <SystemHealthContext.Provider value={value}>{children}</SystemHealthContext.Provider>;
}

export function useSystemHealth() {
  const value = useContext(SystemHealthContext);
  if (!value) throw new Error("useSystemHealth must be used inside SystemHealthProvider");
  return value;
}
