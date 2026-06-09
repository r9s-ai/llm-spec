#!/usr/bin/env bash
set -euo pipefail

# Centralized entrypoint for usage-producing audit cases.
# Override these env vars at call time when auditing a different provider/case.
export TARGET_PROVIDERS="${TARGET_PROVIDERS:-gemini,openai,anthropic}"
DEFAULT_TARGET_CASES=(
  "gemini:audio_input"
  "gemini:image_input"
  "gemini:video_input"
  "openai:input_text_image"
  "anthropic:image_source_media_type"
)
DEFAULT_TARGET_CASES_CSV="$(IFS=,; echo "${DEFAULT_TARGET_CASES[*]}")"
export TARGET_CASES="${TARGET_CASES:-$DEFAULT_TARGET_CASES_CSV}"
export BILLING_AUDIT_USAGE_CAPTURE=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# packages/llm-spec is 4 levels up from this script:
# scripts/ -> r9s-billing-audit-workflow/ -> skills/ -> billing-audit/ -> src/
PACKAGE_DIR="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"
cd "$PACKAGE_DIR"
pnpm dlx tsx src/index.ts
