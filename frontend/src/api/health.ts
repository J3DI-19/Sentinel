export type ServiceStatus = {
  status?: string;
  service: string;
  available?: boolean;
  model?: string;
  model_installed?: boolean;
};

export async function getHealth(path: string): Promise<ServiceStatus> {
  const endpoint = path ? `/api/v1/health/${path}` : "/api/v1/health";
  const response = await fetch(endpoint);
  if (!response.ok) throw new Error(`Health request failed: ${response.status}`);
  return response.json() as Promise<ServiceStatus>;
}

export async function getSystemStatus(): Promise<ServiceStatus[]> {
  const results = await Promise.allSettled([getHealth(""), getHealth("db"), getHealth("ai")]);
  return results.map((result, index) =>
    result.status === "fulfilled"
      ? result.value
      : { service: ["api", "database", "ollama"][index], status: "unavailable" },
  );
}

