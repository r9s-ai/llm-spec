export type PageKey = "testing" | "suites" | "settings";

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

export type RunJob = {
  id: string;
  status: string;
  mode: string;
  provider: string;
  endpoint: string;
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

export type TomlSettings = {
  path: string;
  content: string;
  exists: boolean;
};
