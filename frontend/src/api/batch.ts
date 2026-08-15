import { ApiClient, serializeQuery } from "./client";
import type { components } from "./generated";

export type ApiCase = components["schemas"]["CasePublic"];

export interface Page<T> { items: T[]; page: number; page_size: number; total: number }

export const apiClient = new ApiClient("/api/v1");

export const batchApi = {
  listCases(signal?: AbortSignal) {
    return apiClient.request<Page<ApiCase>>(`/cases${serializeQuery({ page: 1, page_size: 100 })}`, { signal });
  },
  createCase(name: string, description = "", signal?: AbortSignal) {
    return apiClient.request<ApiCase>("/cases", {
      method: "POST", signal, headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    });
  },
};
