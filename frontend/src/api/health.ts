export type ServiceStatus = {
  status?: string;
  service: string;
  available?: boolean;
  model?: string;
  model_installed?: boolean;
};

async function getHealth(path: string): Promise<ServiceStatus> {
  return apiClient.request<ServiceStatus>(path ? `/health/${path}` : "/health");
}

export async function getSystemStatus(): Promise<ServiceStatus[]> {
  const results = await Promise.allSettled([getHealth(""), getHealth("db"), getHealth("ai")]);
  return results.map((result, index) =>
    result.status === "fulfilled"
      ? result.value
      : { service: ["api", "database", "ollama"][index], status: "unavailable" },
  );
}
import { apiClient } from "./batch";
