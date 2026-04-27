#!/usr/bin/env bash
set -euo pipefail

# Centralized entrypoint for usage-producing audit cases.
# Override these env vars at call time when auditing a different provider/case.
export TARGET_PROVIDERS="${TARGET_PROVIDERS:-gemini,openai,anthropic}"
export TARGET_CASES="${TARGET_CASES:-audit_*}"

pnpm dlx tsx src/index.ts
