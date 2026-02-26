.PHONY: help pre-commit-install pre-commit pre-commit-all pre-commit-files pre-commit-update \
	llm-spec-run-all llm-spec-run-openai llm-spec-run-anthropic llm-spec-run-gemini llm-spec-run-xai \
	test-core test-integration test-mock-all test-mock-openai test-mock-anthropic \
	web-backend web-frontend

PRE_COMMIT ?= pre-commit
LLM_SPEC_WEB_DATABASE_URL ?= sqlite:///./packages/web-api/src/llm_spec_web/.data/llm_spec_web.db
LLM_SPEC_WEB_APP_TOML_PATH ?= llm-spec.toml
LLM_SPEC_WEB_AUTO_INIT_DB ?= true

help:
	@echo "Targets:"
	@echo "  pre-commit-install  Install git hooks"
	@echo "  pre-commit          Run hooks on staged files"
	@echo "  pre-commit-all      Run hooks on all files"
	@echo "  pre-commit-files    Run hooks on given files (make pre-commit-files FILES='a.py b.py')"
	@echo "  pre-commit-update   Update hook revisions"
	@echo ""
	@echo "  llm-spec-run-all       Run all suites"
	@echo "  llm-spec-run-openai    Run OpenAI suites"
	@echo "  llm-spec-run-anthropic Run Anthropic suites"
	@echo "  llm-spec-run-gemini    Run Gemini suites"
	@echo "  llm-spec-run-xai       Run xAI suites"
	@echo ""
	@echo "  test-mock-all          Run all integration tests in mock mode"
	@echo "  test-mock-openai       Run OpenAI integration tests in mock mode"
	@echo "  test-mock-anthropic    Run Anthropic integration tests in mock mode"
	@echo "  test-core              Run unit tests under packages/core/tests/unit"
	@echo "  test-integration       Run integration tests under packages/core/tests/integration"
	@echo "  web-backend            Start FastAPI backend from packages/web-api"
	@echo "  web-frontend           Start frontend dev server from packages/web"

pre-commit-install:
	@$(PRE_COMMIT) install

pre-commit:
	@$(PRE_COMMIT) run

pre-commit-all:
	@$(PRE_COMMIT) run --all-files

pre-commit-files:
	@test -n "$(FILES)" || (echo "FILES is required (e.g. make pre-commit-files FILES='path/to/file.py')" && exit 2)
	@$(PRE_COMMIT) run --files $(FILES)

pre-commit-update:
	@$(PRE_COMMIT) autoupdate

# --- llm-spec run commands (real API) ---
llm-spec-run-all:
	uv run python -m llm_spec run
llm-spec-run-openai:
	uv run python -m llm_spec run --provider openai
llm-spec-run-anthropic:
	uv run python -m llm_spec run --provider anthropic
llm-spec-run-gemini:
	uv run python -m llm_spec run --provider gemini
llm-spec-run-xai:
	uv run python -m llm_spec run --provider xai

# --- Integration tests (Mock mode) ---
test-core:
	uv run pytest packages/core/tests/unit -v

test-integration:
	uv run pytest packages/core/tests/integration -v

test-mock-all:
	uv run pytest packages/core/tests/integration/test_suite_runner.py --mock -v
test-mock-openai:
	uv run pytest packages/core/tests/integration/test_suite_runner.py --mock -k "openai" -v
test-mock-anthropic:
	uv run pytest packages/core/tests/integration/test_suite_runner.py --mock -k "anthropic" -v

# --- Web backend helpers ---
web-backend:
	LLM_SPEC_WEB_DATABASE_URL=$(LLM_SPEC_WEB_DATABASE_URL) \
	LLM_SPEC_WEB_APP_TOML_PATH=$(LLM_SPEC_WEB_APP_TOML_PATH) \
	LLM_SPEC_WEB_AUTO_INIT_DB=$(LLM_SPEC_WEB_AUTO_INIT_DB) \
	uv run python -m llm_spec_web.main

web-frontend:
	cd packages/web && pnpm dev
