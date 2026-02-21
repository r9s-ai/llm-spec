-- Migration: Add name column to run_batch table
-- Run this migration if the table already exists without the name column

ALTER TABLE run_batch ADD COLUMN IF NOT EXISTS name varchar(255) NOT NULL DEFAULT 'Task';
