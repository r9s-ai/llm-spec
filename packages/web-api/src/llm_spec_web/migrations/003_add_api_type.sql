-- Migration: Add api_type column to provider_config table
-- This field identifies which API vendor the provider uses

ALTER TABLE provider_config
ADD COLUMN IF NOT EXISTS api_type VARCHAR(32) NOT NULL DEFAULT 'openai';

-- Update existing records to set api_type based on provider name
UPDATE provider_config
SET api_type = provider
WHERE api_type = 'openai' AND provider IN ('openai', 'anthropic', 'gemini', 'xai');
