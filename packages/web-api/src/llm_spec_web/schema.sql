-- llm-spec web backend schema (SQLite)
-- Suites are loaded from suites-registry files.
-- Provider configs are loaded from llm-spec.toml.

PRAGMA foreign_keys = ON;

create table if not exists run_batch (
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

create index if not exists ix_run_batch_status on run_batch(status);
create index if not exists ix_run_batch_created_at on run_batch(created_at desc);

create table if not exists run_job (
    id text primary key,
    status text not null default 'queued',
    mode text not null default 'real',
    provider text not null,
    route text null,
    model text null,
    endpoint text not null,
    batch_id text references run_batch(id) on delete cascade,
    suite_version_id text null,
    config_snapshot text not null default '{}',
    started_at text null,
    finished_at text null,
    progress_total integer not null default 0,
    progress_done integer not null default 0,
    progress_passed integer not null default 0,
    progress_failed integer not null default 0,
    error_message text null
);

create index if not exists ix_run_job_batch_id on run_job(batch_id);
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

create table if not exists run_test_result (
    id text primary key,
    run_id text not null references run_job(id) on delete cascade,
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
