-- Migration: Add run_batch table and batch_id to run_job
-- Run this script to upgrade existing database

-- 1. Create run_batch table
create table if not exists run_batch (
    id varchar(36) primary key,
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

-- 2. Add batch_id column to run_job (if not exists)
-- PostgreSQL doesn't have "ADD COLUMN IF NOT EXISTS", so we use a DO block
do $$
begin
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'run_job' and column_name = 'batch_id'
    ) then
        alter table run_job add column batch_id varchar(36) references run_batch(id) on delete cascade;
    end if;
end $$;

-- 3. Create index on batch_id
create index if not exists ix_run_job_batch_id on run_job(batch_id);

-- Done! Existing data is preserved.
-- Note: Existing run_job records will have batch_id = NULL (they were created before batch feature)
