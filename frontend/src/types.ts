// Page types
export type PageKey = "testing" | "suites" | "settings";

// Run mode
export type RunMode = "real" | "mock";

// Suite types
export type Suite = {
  id: string;
  provider: string;
  endpoint: string;
  name: string;
  status: string;
  latest_version: number;
  created_at: string;
  updated_at: string;
};

export type SuiteVersion = {
  id: string;
  suite_id: string;
  version: number;
  created_by: string;
  created_at: string;
  raw_json5: string;
  parsed_json: Record<string, unknown>;
};

// Run batch types
export type RunBatch = {
  id: string;
  name: string;
  status: string;
  mode: string;
  total_runs: number;
  completed_runs: number;
  passed_runs: number;
  failed_runs: number;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};

export type RunBatchWithRuns = RunBatch & {
  runs: RunJob[];
};

// Run types
export type RunJob = {
  id: string;
  status: string;
  mode: string;
  provider: string;
  endpoint: string;
  batch_id: string | null;
  suite_version_id: string | null;
  started_at: string | null;
  finished_at: string | null;
  progress_total: number;
  progress_done: number;
  progress_passed: number;
  progress_failed: number;
  error_message: string | null;
};

export type RunEvent = {
  id: number;
  run_id: string;
  seq: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
};

// Settings types
export type TomlSettings = {
  path: string;
  content: string;
  exists: boolean;
};

// Provider config types
export type ApiType = "openai" | "anthropic" | "gemini" | "xai";

export type ProviderConfig = {
  provider: string;
  api_type: ApiType;
  base_url: string;
  timeout: number;
  extra_config: Record<string, unknown>;
  updated_at: string;
};

export type ProviderConfigUpsert = {
  api_type?: ApiType;
  base_url: string;
  timeout?: number;
  api_key?: string; // Optional for updates - if not provided, keep existing
  extra_config?: Record<string, unknown>;
};

// Test types
export type TestRow = {
  name: string;
  paramName: string;
  valueText: string;
};

// Selection types
export type TestSelectionMap = Record<string, Set<string>>;
export type VersionsMap = Record<string, SuiteVersion[]>;

// Run result summary
export type RunSummary = {
  total?: number;
  passed?: number;
  failed?: number;
};

// API request types
export type CreateSuiteInput = {
  provider: string;
  endpoint: string;
  name: string;
  raw_json5: string;
  created_by: string;
};

export type UpdateSuiteInput = {
  name?: string;
  status?: "active" | "archived";
};

export type CreateVersionInput = {
  raw_json5: string;
  created_by: string;
};

export type CreateRunInput = {
  suite_version_id: string;
  mode?: RunMode;
  selected_tests?: string[];
};
