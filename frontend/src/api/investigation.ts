import { apiClient, type Page } from "./batch";
import { serializeQuery } from "./client";

export interface InvestigationFilters { page?: number; pageSize?: number; source?: string; eventType?: string; entity?: string; severity?: string; startTime?: string; endTime?: string; }
export const investigationApi = {
  summary(caseId: number, signal?: AbortSignal) { return apiClient.request<Record<string, unknown>>(`/cases/${caseId}/summary`, { signal }); },
  list(caseId: number, section: string, filters: InvestigationFilters, signal?: AbortSignal) {
    const query = serializeQuery({ page: filters.page ?? 1, page_size: filters.pageSize ?? 50, source: filters.source, event_type: filters.eventType, entity: filters.entity, severity: filters.severity, start_time: filters.startTime, end_time: filters.endTime });
    return apiClient.request<Page<Record<string, unknown>>>(`/cases/${caseId}/${section}${query}`, { signal });
  },
  graph(caseId: number, signal?: AbortSignal) { return apiClient.request<{ nodes: Record<string, unknown>[]; edges: Record<string, unknown>[]; truncated: boolean }>(`/cases/${caseId}/graph`, { signal }); },
  aggregates(caseId: number, signal?: AbortSignal) { return apiClient.request<Page<Record<string, unknown>>>(`/cases/${caseId}/aggregates`, { signal }); },
  reanalyze(caseId: number, signal?: AbortSignal) { return apiClient.request<Record<string, unknown>>(`/cases/${caseId}/analyses`, { method: "POST", signal }); },
};
