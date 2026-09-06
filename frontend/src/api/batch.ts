import { ApiClient, serializeQuery } from "./client";
import type { components } from "./generated";

export type ApiCase = components["schemas"]["CasePublic"];
export type ApiCasePage = components["schemas"]["PageResponse_CasePublic_"];

export const apiClient = new ApiClient("/api/v1");

export const batchApi = {
  listCases(signal?: AbortSignal) {
    return apiClient.request<ApiCasePage>(`/cases${serializeQuery({ page: 1, page_size: 100 })}`, { signal });
  },
  createCase(name: string, description = "", owner = "Investigator", signal?: AbortSignal) {
    return apiClient.request<ApiCase>("/cases", {
      method: "POST", signal, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description, owner }),
    });
  },
};
