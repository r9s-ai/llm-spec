-- llm-spec web backend initial schema (PostgreSQL)

create table if not exists suite (
    id varchar(36) primary key,
    provider varchar(32) not null,
    endpoint varchar(255) not null,
    name varchar(255) not null,
    status varchar(16) not null default 'active',
    latest_version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_suite_provider_endpoint unique (provider, endpoint)
);

create table if not exists suite_version (
    id varchar(36) primary key,
    suite_id varchar(36) not null references suite(id) on delete cascade,
    version integer not null,
    raw_json5 text not null,
    parsed_json jsonb not null,
    created_by varchar(128) not null default 'system',
    created_at timestamptz not null default now(),
    constraint uq_suite_version unique (suite_id, version)
);

create table if not exists provider_config (
    provider varchar(32) primary key,
    base_url varchar(512) not null,
    timeout double precision not null default 30.0,
    api_key text not null,
    extra_config jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

-- Run batch table (represents a test task containing multiple runs)
create table if not exists run_batch (
    id varchar(36) primary key,
    name varchar(255) not null default 'Task',
    status varchar(16) not null default 'running',
    mode varchar(16) not null default 'real',
    total_runs integer not null default 0,
    completed_runs integer not null default 0,
    passed_runs integer not null default 0,
    failed_runs integer not null default 0,
    started_at timestamptz null,
    finished_at timestamptz null,
    created_at timestamptz not null default now()
);

create index if not exists ix_run_batch_status on run_batch(status);
create index if not exists ix_run_batch_created_at on run_batch(created_at desc);

create table if not exists run_job (
    id varchar(36) primary key,
    status varchar(16) not null default 'queued',
    mode varchar(16) not null default 'real',
    provider varchar(32) not null,
    endpoint varchar(255) not null,
    batch_id varchar(36) references run_batch(id) on delete cascade,
    suite_version_id varchar(36) references suite_version(id) on delete set null,
    config_snapshot jsonb not null default '{}'::jsonb,
    started_at timestamptz null,
    finished_at timestamptz null,
    progress_total integer not null default 0,
    progress_done integer not null default 0,
    progress_passed integer not null default 0,
    progress_failed integer not null default 0,
    error_message text null
);

create index if not exists ix_run_job_batch_id on run_job(batch_id);

create table if not exists run_event (
    id bigserial primary key,
    run_id varchar(36) not null references run_job(id) on delete cascade,
    seq integer not null,
    event_type varchar(64) not null,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint uq_run_event_seq unique (run_id, seq)
);

create table if not exists run_result (
    run_id varchar(36) primary key references run_job(id) on delete cascade,
    run_result_json jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists run_test_result (
    id varchar(36) primary key,
    run_id varchar(36) not null references run_job(id) on delete cascade,
    test_id varchar(512) not null,
    test_name varchar(255) not null,
    parameter_name varchar(255) not null,
    parameter_value jsonb null,
    status varchar(16) not null,
    fail_stage varchar(32) null,
    reason_code varchar(64) null,
    latency_ms integer null,
    raw_record jsonb not null
);

create index if not exists ix_run_job_provider_status on run_job(provider, status);
create index if not exists ix_run_test_result_run_status on run_test_result(run_id, status);
create index if not exists ix_suite_provider on suite(provider);
create index if not exists ix_suite_endpoint on suite(endpoint);
