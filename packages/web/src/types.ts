// Page types
export type PageKey = "testing" | "suites" | "settings";

// Run mode
export type RunMode = "real" | "mock";

// Suite types
export type SuiteTestDef = {
  name: string;
  description: string;
  baseline: boolean;
  check_stream: boolean;
  focus_name: string | null;
  focus_value: unknown;
  tags: string[];
};

export type Suite = {
  suite_id: string;
  suite_name: string;
  provider_id: string;
  model_id: string;
  route_id: string;
  api_family: string;
  endpoint: string;
  method: string;
  tests: SuiteTestDef[];
};

// Task types
export type Task = {
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

export type TaskWithRuns = Task & {
  runs: RunJob[];
};

// Run types
export type RunJob = {
  id: string;
  status: string;
  mode: string;
  provider: string;
  route: string | null;
  model: string | null;
  endpoint: string;
  task_id: string | null;
  suite_id: string | null;
  suite_name: string | null;
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

export type ApiType = "openai" | "anthropic" | "gemini" | "xai";

export type ProviderConfig = {
  provider: string;
  api_type: ApiType;
  base_url: string;
  timeout: number;
  api_key: string;
  extra_config: Record<string, unknown>;
  updated_at: string;
};

export type ProviderConfigUpsert = {
  api_type: ApiType;
  base_url: string;
  timeout: number;
  api_key?: string;
  extra_config?: Record<string, unknown>;
};

// Test types
export type TestRow = {
  name: string;
  paramName: string;
  valueText: string;
  tags: string[];
};

// Selection types
export type TestSelectionMap = Record<string, Set<string>>;

// Run result summary
export type RunSummary = {
  total?: number;
  passed?: number;
  failed?: number;
};

// Shared test result row shape used by result tables and run cards
export type TestResultRow = {
  run_case_id?: string;
  test_name: string;
  status?: "pending" | "running" | "pass" | "fail";
  parameter?: {
    name: string;
    value: unknown;
    value_type: string;
  };
  request?: {
    http_status: number;
    latency_ms: number;
  };
  result?: {
    status: string;
    reason?: string;
  };
  validation?: {
    schema_ok: boolean;
    required_fields_ok: boolean;
    stream_rules_ok: boolean;
    missing_fields: string[];
    missing_events: string[];
  };
};
