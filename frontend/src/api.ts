export type MemoryType =
  | "axiom"
  | "preference"
  | "project"
  | "person"
  | "decision"
  | "concept"
  | "source"
  | "task"
  | "event"
  | "artifact"
  | "skill"
  | "system"
  | "note";

export type Cadence = "none" | "daily" | "weekly" | "monthly" | "seasonal";

export type SearchScope = "general" | "remembering";

export type SourceLink = {
  id: string;
  memory_id: string;
  label: string;
  kind: string;
  uri: string;
  open_hint: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type Memory = {
  id: string;
  type: MemoryType;
  content: string;
  happened_at: string;
  created_at: string;
  updated_at: string;
  source: string;
  source_links: SourceLink[];
  cadence: Cadence;
  expires_at: string | null;
  base_importance: number;
  access_count: number;
  axiom_key: string | null;
  version: number;
  supersedes_id: string | null;
  is_current: boolean;
  metadata: Record<string, unknown>;
  rank: number | null;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8765";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "content-type": "application/json",
      ...init?.headers,
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function listMemories(): Promise<Memory[]> {
  return request<Memory[]>("/memories?limit=100");
}

export function searchMemories(
  query: string,
  scope: SearchScope,
): Promise<{ query: string; results: Memory[] }> {
  return request<{ query: string; results: Memory[] }>("/search", {
    method: "POST",
    body: JSON.stringify({ query, limit: 12, scope }),
  });
}

export function createMemory(payload: {
  type: MemoryType;
  content: string;
  cadence: Cadence;
  base_importance: number;
  source: string;
  axiom_key?: string;
  source_links?: Array<{
    label: string;
    kind: string;
    uri: string;
    open_hint?: string;
  }>;
}): Promise<Memory> {
  return request<Memory>("/memories", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function navigateMemory(memoryId: string): Promise<{
  origin: Memory;
  connections: Memory[];
}> {
  return request<{ origin: Memory; connections: Memory[] }>(
    `/memories/${memoryId}/navigate?limit=10`,
  );
}
