import type {
  RunBatch,
  RunBatchWithRuns,
  RunEvent,
  RunJob,
  Suite,
  SuiteVersion,
  TomlSettings,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function getSuites(): Promise<Suite[]> {
  return request<Suite[]>("/api/suites");
}

export function createSuite(input: {
  provider: string;
  endpoint: string;
  name: string;
  raw_json5: string;
  created_by: string;
}): Promise<Suite> {
  return request<Suite>("/api/suites", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateSuite(
  suiteId: string,
  input: { name?: string; status?: "active" | "archived" }
): Promise<Suite> {
  return request<Suite>(`/api/suites/${suiteId}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function deleteSuite(suiteId: string): Promise<void> {
  return request<void>(`/api/suites/${suiteId}`, { method: "DELETE" });
}

export function listVersions(suiteId: string): Promise<SuiteVersion[]> {
  return request<SuiteVersion[]>(`/api/suites/${suiteId}/versions`);
}

export function createVersion(
  suiteId: string,
  input: { raw_json5: string; created_by: string }
): Promise<SuiteVersion> {
  return request<SuiteVersion>(`/api/suites/${suiteId}/versions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

// Batch API functions
export function createBatch(input: {
  suite_version_ids: string[];
  mode?: "real" | "mock";
  selected_tests_by_suite?: Record<string, string[]>;
  name?: string;
  max_concurrent?: number;
}): Promise<RunBatchWithRuns> {
  return request<RunBatchWithRuns>("/api/batches", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getBatches(options?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<RunBatch[]> {
  const params = new URLSearchParams();
  if (options?.status) params.set("status", options.status);
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.offset) params.set("offset", String(options.offset));
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<RunBatch[]>(`/api/batches${query}`);
}

export function getBatch(batchId: string): Promise<RunBatchWithRuns> {
  return request<RunBatchWithRuns>(`/api/batches/${batchId}`);
}

export function updateBatch(batchId: string, name: string): Promise<RunBatch> {
  return request<RunBatch>(`/api/batches/${batchId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function deleteBatch(batchId: string): Promise<void> {
  return request<void>(`/api/batches/${batchId}`, { method: "DELETE" });
}

export function getBatchRuns(batchId: string): Promise<RunJob[]> {
  return request<RunJob[]>(`/api/batches/${batchId}/runs`);
}

// Run API functions
export function createRun(input: {
  suite_version_id: string;
  mode?: "real" | "mock";
  selected_tests?: string[];
}): Promise<RunJob> {
  return request<RunJob>("/api/runs", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getRun(runId: string): Promise<RunJob> {
  return request<RunJob>(`/api/runs/${runId}`);
}

export function getRunResult(runId: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/api/runs/${runId}/result`);
}

export function getRunEvents(runId: string, afterSeq = 0): Promise<RunEvent[]> {
  return request<RunEvent[]>(`/api/runs/${runId}/events?after_seq=${afterSeq}`);
}

export function streamRunEvents(runId: string, afterSeq = 0): EventSource {
  return new EventSource(`${BASE_URL}/api/runs/${runId}/events/stream?after_seq=${afterSeq}`);
}

export function getTomlSettings(): Promise<TomlSettings> {
  return request<TomlSettings>("/api/settings/toml");
}

export function updateTomlSettings(content: string): Promise<TomlSettings> {
  return request<TomlSettings>("/api/settings/toml", {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}
