-- llm-spec web backend schema (SQLite)
-- Suites are loaded from suites-registry files.
-- Provider configs are loaded from llm-spec.toml.

PRAGMA foreign_keys = ON;

create table if not exists task (
    id text primary key,
    name text not null default 'Task',
    status text not null default 'running',
    mode text not null default 'real',
    total_runs integer not null default 0,
    completed_runs integer not null default 0,
    passed_runs integer not null default 0,
    failed_runs integer not null default 0,
    started_at text null,
    finished_at text null,
    created_at text not null default (datetime('now'))
);

create index if not exists ix_task_status on task(status);
create index if not exists ix_task_created_at on task(created_at desc);

create table if not exists run_job (
    id text primary key,
    status text not null default 'queued',
    mode text not null default 'real',
    provider text not null,
    route text null,
    model text null,
    endpoint text not null,
    task_id text references task(id) on delete cascade,
    model_suite_id text null,
    selected_tests text not null default '[]',
    started_at text null,
    finished_at text null,
    progress_total integer not null default 0,
    progress_done integer not null default 0,
    progress_passed integer not null default 0,
    progress_failed integer not null default 0,
    error_message text null
);

create index if not exists ix_run_job_task_id on run_job(task_id);
create index if not exists ix_run_job_provider_status on run_job(provider, status);
create index if not exists ix_run_job_provider_model_route on run_job(provider, model, route);

create table if not exists run_event (
    id integer primary key autoincrement,
    run_id text not null references run_job(id) on delete cascade,
    seq integer not null,
    event_type text not null,
    payload text not null default '{}',
    created_at text not null default (datetime('now')),
    constraint uq_run_event_seq unique (run_id, seq)
);

create table if not exists task_result (
    run_id text primary key references run_job(id) on delete cascade,
    task_result_json text not null,
    created_at text not null default (datetime('now'))
);

create table if not exists run_case (
    id text primary key,
    run_id text not null references run_job(id) on delete cascade,
    case_id text not null,
    test_name text not null,
    provider text not null,
    route text null,
    model text null,
    request_method text not null,
    request_endpoint text not null,
    request_params text not null default '{}',
    request_files text null,
    check_stream integer not null default 0,
    response_schema text null,
    stream_chunk_schema text null,
    required_fields text not null default '[]',
    stream_expectations text null,
    parameter_name text null,
    parameter_value text null,
    parameter_value_type text not null default 'none',
    is_baseline integer not null default 0,
    tags text not null default '[]',
    description text not null default '',
    created_at text not null default (datetime('now')),
    constraint uq_run_case_run_case_id unique (run_id, case_id)
);

create index if not exists ix_run_case_run_id on run_case(run_id);
create index if not exists ix_run_case_run_test_name on run_case(run_id, test_name);

create table if not exists run_test_result (
    id text primary key,
    run_id text not null references run_job(id) on delete cascade,
    run_case_id text null references run_case(id) on delete cascade,
    test_id text not null,
    test_name text not null,
    parameter_value text null,
    status text not null,
    fail_stage text null,
    reason_code text null,
    latency_ms integer null,
    raw_record text not null
);

create index if not exists ix_run_test_result_run_status on run_test_result(run_id, status);
create index if not exists ix_run_test_result_run_case_id on run_test_result(run_case_id);
