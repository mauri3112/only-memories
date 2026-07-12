export type MemoryType = "axiom" | "preference" | "project" | "person" | "decision" | "concept" | "source" | "task" | "event" | "artifact" | "skill" | "system" | "note";
export type Cadence = "none" | "daily" | "weekly" | "monthly" | "seasonal";
export type SearchScope = "general" | "remembering";
export type MemoryView = "all" | "axioms" | "forgotten" | "expired";
export type MemoryRelation = "related" | "updates" | "extends" | "derives" | "supports";
export type SourceLink = { id: string; memory_id: string; label: string; kind: string; uri: string; open_hint: string | null; metadata: Record<string, unknown>; created_at: string };
export type Memory = { id: string; type: MemoryType; content: string; happened_at: string; created_at: string; updated_at: string; source: string; source_links: SourceLink[]; cadence: Cadence; expires_at: string | null; base_importance: number; access_count: number; axiom_key: string | null; version: number; supersedes_id: string | null; is_current: boolean; is_forgotten: boolean; forgotten_at: string | null; forget_reason: string | null; metadata: Record<string, unknown>; rank: number | null };
export type Connection = { source_id: string; target_id: string; weight: number; relation: MemoryRelation; reason: string; created_at: string };
export type GraphResponse = { origin: Memory; nodes: Memory[]; edges: Connection[] };
export type VersionHistory = { current: Memory; versions: Memory[] };
export type MaintenanceProposal = { id: string; run_id: string; type: "retire_expired" | "collapse_duplicate" | "add_connection"; status: "pending" | "applied" | "dismissed"; memory_id: string; target_id: string | null; reason: string; score: number | null; created_at: string; decided_at: string | null };
export type HealthResponse = { status: string; database_path: string };

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: { "content-type": "application/json", ...init?.headers }, ...init });
  if (!response.ok) {
    const detail = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(detail?.detail ?? `API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const health = () => request<HealthResponse>("/health");
export function listMemories(view: MemoryView = "all"): Promise<Memory[]> {
  const params = new URLSearchParams({ limit: "50" });
  if (view === "axioms") params.set("type", "axiom");
  if (view === "forgotten") params.set("include_forgotten", "true");
  if (view === "expired") params.set("include_expired", "true");
  return request<Memory[]>(`/memories?${params}`);
}
export function searchMemories(query: string, scope: SearchScope, view: MemoryView) {
  return request<{ query: string; results: Memory[] }>("/search", {
    method: "POST",
    body: JSON.stringify({
      query,
      limit: 50,
      scope,
      type: view === "axioms" ? "axiom" : undefined,
      include_forgotten: scope === "remembering" || view === "forgotten",
      include_expired: scope === "remembering" || view === "expired",
    }),
  });
}
export const createMemory = (payload: { type: MemoryType; content: string; cadence: Cadence; base_importance: number; source: string; axiom_key?: string; supersedes_id?: string; expires_at?: string | null; source_links?: Array<{ label: string; kind: string; uri: string; open_hint?: string }> }) => request<Memory>("/memories", { method: "POST", body: JSON.stringify(payload) });
export const updateMemory = (id: string, payload: Partial<{ content: string; cadence: Cadence; base_importance: number; expires_at: string | null; source_links: Array<{ label: string; kind: string; uri: string; open_hint?: string }> }>) => request<Memory>(`/memories/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
export const forgetMemory = (id: string, reason?: string) => request<Memory>(`/memories/${id}/forget`, { method: "POST", body: JSON.stringify({ reason }) });
export const restoreMemory = (id: string) => request<Memory>(`/memories/${id}/restore`, { method: "POST" });
export const getGraph = (id: string) => request<GraphResponse>(`/memories/${id}/graph?limit=8`);
export const getVersions = (id: string) => request<VersionHistory>(`/memories/${id}/versions`);
export const previewMaintenance = () => request<{ id: string; created_at: string; proposals: MaintenanceProposal[] }>("/maintenance/preview", { method: "POST" });
export const listMaintenance = () => request<MaintenanceProposal[]>("/maintenance/proposals");
export const decideMaintenance = (id: string, action: "apply" | "dismiss") => request<{ proposal: MaintenanceProposal; memory: Memory | null }>(`/maintenance/proposals/${id}/${action}`, { method: "POST" });
