import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, ChangeEvent, ReactNode } from 'react'
import {
  Bot,
  Check,
  ChevronsUpDown,
  Copy,
  Database,
  Download,
  Eye,
  EyeOff,
  FileJson,
  FolderOpen,
  History,
  Layers,
  Pencil,
  Play,
  Plus,
  ReceiptText,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Server,
  Settings2,
  Trash2,
  Upload,
  Wifi,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  GEMINI_GENERATE_CONTENT_SERVED_MODEL_IDS,
  OPENAI_CHAT_SERVED_MODEL_IDS,
  OPENAI_RESPONSES_SERVED_MODEL_IDS,
  runBrowserStandardCases,
} from '@/lib/browser-runner'
import {
  checkBackendHealth,
  createBackendJob,
  deleteBackendRunHistory,
  listBackendRunHistory,
  loadBackendJobStatus,
  loadBackendRunHistoryReport,
  runBackendCases,
  saveBackendRunReport,
} from '@/lib/backend-client'
import { formatDateTime } from '@/lib/format'
import {
  isCaseRecommendedForModel,
  isGeminiOpenAICompatibilityModel,
  normalizeModelName,
} from '@/lib/model-capabilities'
import { cn } from '@/lib/utils'
import type {
  AgentProvider,
  BackendJobRequest,
  BackendJobStatusResponse,
  BackendRunHistoryEntry,
  PlatformRunConfig,
  R9SBillingAuditConfig,
  RunProgressEvent,
  RunProgressHandler,
  RunSnapshot,
  RunSummary,
  StandardApiType,
} from '@/types'

type StandardExecutionMode = 'browser' | 'backend'
type RunTargetKind = 'standard' | 'agent'

interface StandardRunTarget {
  id: string
  kind: 'standard'
  enabled: boolean
  apiType: StandardApiType
  model: string
  targetCases: string
}

interface AgentRunTarget {
  id: string
  kind: 'agent'
  enabled: boolean
  agentProvider: AgentProvider
  model: string
  targetCases: string
}

type RunTarget = StandardRunTarget | AgentRunTarget

interface SiteProfileConfig {
  apiKey: string
  apiBaseUrl: string
  customHeaders: string
  apiVersion: string
  backendUrl: string
  standardExecution: StandardExecutionMode
  workingDirectory: string
  skipGitRepoCheck: boolean
  testImagePath: string
  r9sBillingAuditEnabled: boolean
  r9sManagerBaseUrl: string
  r9sManagerKey: string
  r9sTokenId: string
}

interface RunSettings {
  timeoutMs: string
  concurrency: string
  failFast: boolean
}

interface RunDraft {
  targets: RunTarget[]
  settings: RunSettings
}

interface ActiveBackendJob {
  id: string
  backendUrl: string
}

interface PlatformConsoleProps {
  onReport: (report: RunSummary) => void
  onLoadFile: (file: File) => void | Promise<void>
  onLoadSample: () => void
  loading: boolean
  error: string | null
}

interface StandardApiOption {
  value: StandardApiType
  label: string
  defaultModel: string
  placeholderBaseUrl: string
}

interface AgentOption {
  value: AgentProvider
  label: string
  defaultModel: string
}

interface TargetCaseOption {
  value: string
  label: string
  group: string
  requiredModels?: readonly string[]
}

const STANDARD_API_OPTIONS: StandardApiOption[] = [
  {
    value: 'openai.chat',
    label: 'OpenAI Chat Completions',
    defaultModel: 'gpt-4o-mini',
    placeholderBaseUrl: 'https://api.openai.com/v1',
  },
  {
    value: 'openai.responses',
    label: 'OpenAI Responses',
    defaultModel: 'gpt-4o-mini',
    placeholderBaseUrl: 'https://api.openai.com/v1',
  },
  {
    value: 'anthropic.messages',
    label: 'Anthropic Messages',
    defaultModel: 'claude-3-5-haiku-latest',
    placeholderBaseUrl: 'https://api.anthropic.com/v1',
  },
  {
    value: 'gemini.generateContent',
    label: 'Gemini generateContent',
    defaultModel: 'gemini-2.5-flash',
    placeholderBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
  },
]

const AGENT_OPTIONS: AgentOption[] = [
  {
    value: 'claude-agent',
    label: 'Claude Agent',
    defaultModel: '',
  },
  {
    value: 'codex',
    label: 'Codex',
    defaultModel: '',
  },
]

const ANTHROPIC_MESSAGES_MODEL_IDS = [
  'claude-sonnet-4-5',
  'claude-sonnet-4-20250514',
  'claude-opus-4-1',
  'claude-opus-4-20250514',
  'claude-haiku-4-5',
  'claude-3-5-haiku-latest',
  'claude-3-haiku-20240307',
] as const

function currentDomainBackendUrl(): string {
  return window.location.origin
}

function isLoopbackBackendUrl(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed) {
    return false
  }

  try {
    const hostname = new URL(trimmed.includes('://') ? trimmed : `http://${trimmed}`).hostname.toLowerCase()
    return (
      hostname === 'localhost' ||
      hostname === '0.0.0.0' ||
      hostname === '::1' ||
      hostname === '[::1]' ||
      /^127(?:\.\d{1,3}){3}$/.test(hostname)
    )
  } catch {
    return false
  }
}

function resolveRuntimeBackendUrl(value: string): string {
  const trimmed = value.trim()
  if (import.meta.env.PROD && isLoopbackBackendUrl(trimmed)) {
    return currentDomainBackendUrl()
  }
  return trimmed
}

const ENV_BACKEND_URL = import.meta.env.VITE_LLM_SPEC_BACKEND_URL?.trim()
const DEFAULT_BACKEND_URL = resolveRuntimeBackendUrl(
  ENV_BACKEND_URL || (import.meta.env.PROD ? currentDomainBackendUrl() : 'http://localhost:8788'),
)

const STANDARD_TARGET_CASES: Record<StandardApiType, TargetCaseOption[]> = {
  'openai.chat': [
    ...caseOptions('Chat', [
      'basic',
      'input_text_image',
      'sampling_and_max_completion',
      'max_tokens_legacy',
      'stop_sequences',
      'stop_string',
      'response_format_text',
      'response_format_json_object',
      'response_format_json_schema',
      'tools_and_tool_choice',
      'tool_choice_variants',
      'parallel_tool_calls_enabled',
      'developer_role_message',
      'tool_role_message',
      'refusal_content_prompt',
      'stream_and_stream_options',
      'basic_stream',
      'sampling_and_max_completion_stream',
      'max_tokens_legacy_stream',
      'stop_sequences_stream',
      'response_format_json_object_stream',
      'response_format_json_schema_stream',
      'tools_and_tool_choice_stream',
      'prompt_cache_explicit_breakpoint_round_trip',
    ]),
    ...caseOptions('OpenAI-specific', [
      'n_choices',
      'identity_metadata_caching',
      'prompt_cache_round_trip',
      'logprobs',
      'logit_bias',
      'legacy_functions',
      'prediction_and_verbosity',
      'reasoning_effort',
      'web_search_options',
      'audio_modalities',
    ]),
    ...modelCatalogCaseOptions('OpenAI model catalog', 'model_', OPENAI_CHAT_SERVED_MODEL_IDS),
    ...caseOptions('Gemini compatibility', [
      'gemini_message_roles_and_name',
      'gemini_multimodal_image_input',
      'gemini_reasoning_effort_variants',
      'gemini_tool_choice_variants',
      'gemini_stream_includes_usage',
      'gemini_extra_body_native_params',
      'gemini_prompt_cache_round_trip',
      'gemini_n_is_limited',
      'gemini_logit_bias_limited',
      'gemini_response_envelope_and_usage',
    ]),
  ],
  'openai.responses': [
    ...caseOptions('Responses', [
      'responses_basic',
      'responses_input_array_text',
      'responses_input_text_image',
      'responses_input_file_detail',
      'responses_assistant_phase_replay',
      'responses_sampling_and_limits',
      'responses_background_and_instructions',
      'responses_identity_and_cache',
      'responses_prompt_cache_round_trip',
      'responses_prompt_cache_explicit_breakpoint_round_trip',
      'responses_prompt_cache_retention_24h',
      'responses_context_include_truncation',
      'responses_text_json_schema',
      'responses_text_format_variants',
      'responses_tools',
      'responses_tool_choice_variants',
      'responses_parallel_tool_calls_enabled',
      'responses_tool_web_search',
      'responses_tool_code_interpreter',
      'responses_tool_file_search',
      'responses_previous_response_id',
      'responses_conversation',
      'responses_stream_and_options',
      'responses_basic_stream',
      'responses_sampling_and_limits_stream',
      'responses_background_and_instructions_stream',
      'responses_identity_and_cache_stream',
      'responses_context_include_truncation_stream',
      'responses_text_json_schema_stream',
      'responses_tools_stream',
      'responses_previous_response_id_stream',
      'responses_conversation_stream',
      'responses_reasoning',
      'responses_reasoning_stream',
      'responses_prompt',
      'responses_prompt_stream',
      'responses_reasoning_effort_variants',
      'responses_store_false',
    ]),
    ...modelCatalogCaseOptions(
      'OpenAI Responses model catalog',
      'responses_model_',
      OPENAI_RESPONSES_SERVED_MODEL_IDS,
    ),
  ],
  'anthropic.messages': [
    ...caseOptions('Messages', [
      'basic',
      'message_role_system',
      'mid_conversation_system_block',
      'usage_output_tokens_details',
      'different_model_haiku',
      'different_model_opus',
      'sampling_and_stop',
      'temperature_sampling',
      'system_metadata_service_tier',
      'container',
      'image_source_media_type',
      'image_source_type_url',
      'output_config_json_schema',
      'service_tier_variants',
      'tools_auto_choice',
      'tools_forced_choice',
      'tool_result_tool_reference',
      'tool_choice_any_none_variants',
      'thinking',
      'cache_control',
      'cache_control_round_trip',
      'cache_control_round_trip_5m',
      'cache_control_round_trip_1h',
      'cache_control_round_trip_top_level',
      'max_tokens_zero_cache_warm',
      'inference_geo',
      'stop_details_refusal',
      'web_fetch_20260309_use_cache',
      'web_fetch_tool_result_error_url_not_in_prior_context',
    ]),
    ...caseOptions('Streaming', [
      'stream',
      'basic_stream',
      'sampling_and_stop_stream',
      'temperature_sampling_stream',
      'system_metadata_service_tier_stream',
      'output_config_json_schema_stream',
      'tools_auto_choice_stream',
      'tools_forced_choice_stream',
      'stream_tool_use_any',
      'thinking_stream',
      'cache_control_stream',
      'cache_control_round_trip_stream',
      'inference_geo_stream',
    ]),
    ...caseOptions('Beta', [
      'beta_prompt_caching',
      'beta_token_counting',
      'beta_token_efficient_tools',
      'beta_output_128k',
      'beta_files_api',
      'beta_code_execution',
      'beta_extended_cache_ttl',
      'beta_context_1m',
      'beta_context_management',
      'beta_model_context_window_exceeded',
      'beta_message_batches',
      'beta_computer_use_2024',
      'beta_computer_use_2025',
      'beta_pdfs',
      'beta_mcp_client_2025_04',
      'beta_mcp_client_2025_11',
      'beta_dev_full_thinking',
      'beta_interleaved_thinking',
      'beta_skills',
      'beta_fast_mode',
      'fast_mode_basic',
      'fast_mode_stream',
      'fast_mode_with_tools',
      'fast_mode_with_thinking',
      'beta_multiple_headers',
      'beta_custom_from_env',
      'beta_prompt_caching_stream',
      'beta_code_execution_stream',
      'beta-probe-server',
    ]),
  ],
  'gemini.generateContent': [
    ...caseOptions('Generate Content', [
      'basic',
      'audio_input',
      'image_input',
      'video_input',
      'sampling_and_limits',
      'candidate_count_multiple',
      'penalties',
      'logprobs',
      'system_labels_http_abort',
      'response_schema',
      'response_json_schema',
      'safety_settings',
      'safety_settings_variants',
      'tools_and_tool_config',
      'tool_config_mode_variants',
      'automatic_function_calling',
      'thinking_config',
      'labels',
      'cached_content',
      'audio_modality',
      'image_config',
      'image_response_modalities_text_image',
      'image_google_search_tool',
      'routing_and_model_selection',
      'model_armor',
    ]),
    ...caseOptions('Streaming', [
      'stream',
      'basic_stream',
      'sampling_and_limits_stream',
      'candidate_count_multiple_stream',
      'penalties_stream',
      'logprobs_stream',
      'system_labels_http_abort_stream',
      'response_schema_stream',
      'response_json_schema_stream',
      'safety_settings_stream',
      'tools_and_tool_config_stream',
      'automatic_function_calling_stream',
      'thinking_config_stream',
      'labels_stream',
      'cached_content_stream',
      'routing_and_model_selection_stream',
    ]),
    ...modelCatalogCaseOptions(
      'Gemini model catalog',
      'model_',
      GEMINI_GENERATE_CONTENT_SERVED_MODEL_IDS,
    ),
  ],
}

const CLAUDE_AGENT_BETA_CATALOG_BETAS = [
  'vertex-2023-10-16',
  'bedrock-2023-05-31',
  'web-search-2025-03-05',
  'files-api-2025-04-14',
  'oauth-2025-04-20',
  'interleaved-thinking-2025-05-14',
  'context-management-2025-06-27',
  'ccr-byoc-2025-07-29',
  'context-1m-2025-08-07',
  'environments-2025-11-01',
  'effort-2025-11-24',
  'token-counting-2024-11-01',
  'message-batches-2024-09-24',
  'skills-2025-10-02',
  'tool-search-tool-2025-10-19',
  'tool-examples-2025-10-29',
  'advanced-tool-use-2025-11-20',
  'mcp-client-2025-11-20',
  'structured-outputs-2025-11-13',
  'structured-outputs-2025-12-15',
  'mcp-servers-2025-12-04',
  'compact-2026-01-12',
  'prompt-caching-scope-2026-01-05',
  'afk-mode-2026-01-31',
  'fast-mode-2026-02-01',
  'redact-thinking-2026-02-12',
] as const

const AGENT_TARGET_CASES: Record<AgentProvider, TargetCaseOption[]> = {
  'claude-agent': [
    ...caseOptions('Session', [
      'basic_prompt',
      'basic_session',
      'streaming_session',
      'multi_turn_conversation',
      'structured_output_json',
      'empty_and_special_prompts',
      'streaming_message_types',
      'prompt_with_context',
      'assistant_message_streaming',
      'large_prompt_handling',
    ]),
    ...caseOptions('Model And Metadata', [
      'different_model_opus',
      'different_model_haiku',
      'system_message_analysis',
      'result_message_metadata',
    ]),
    ...caseOptions('Tools', [
      'tool_combination',
      'tool_execution_with_session',
      'multiple_tools_different_types',
    ]),
    ...caseOptions('Errors', [
      'error_handling_invalid_model',
      'error_during_execution_handling',
    ]),
    ...caseOptions('Beta Context', [
      'beta_context_1m_basic',
      'beta_context_1m_with_session',
      'beta_context_1m_system_message',
      'beta_context_1m_opus',
      'beta_context_1m_haiku',
      'beta_invalid_feature',
      'beta_empty_array',
      'beta_with_tools',
      'beta_context_1m_streaming',
      'beta_context_1m_multi_turn',
      'beta_context_1m_resume_session',
      'beta_context_1m_with_custom_env',
      'beta_context_1m_error_recovery',
      'beta_context_1m_with_effort',
    ]),
    ...caseOptions('Beta Thinking And Effort', [
      'beta_thinking_adaptive',
      'beta_thinking_enabled',
      'beta_thinking_disabled',
      'beta_effort_low',
      'beta_effort_high',
      'beta_effort_max',
      'beta_effort_with_thinking',
      'beta_thinking_effort_context_1m',
    ]),
    ...caseOptions('Beta MCP', [
      'beta_mcp_servers_config',
    ]),
    ...betaCatalogCaseOptions('Beta Catalog', CLAUDE_AGENT_BETA_CATALOG_BETAS),
  ],
  codex: caseOptions('Thread', [
    'basic_thread',
    'basic_thread_streaming',
    'structured_output',
    'structured_output_streaming',
    'multi_turn_conversation',
    'image_input',
    'resume_thread',
    'config_override',
    'env_control',
    'abort_signal',
    'thread_events',
    'usage_tracking',
  ]),
}

const LEGACY_CLAUDE_AGENT_SELECTED_CASES = new Set([
  'basic_prompt',
  'basic_session',
  'streaming_session',
  'multi_turn_conversation',
  'structured_output_json',
  'prompt_with_context',
  'tool_combination',
  'tool_execution_with_session',
  'multiple_tools_different_types',
  'beta_context_1m_basic',
  'beta_context_1m_with_session',
  'beta_thinking_adaptive',
  'beta_thinking_enabled',
  'beta_effort_low',
  'beta_effort_high',
  'beta_mcp_servers_config',
])

function caseOptions(
  group: string,
  values: readonly string[],
  modelRequirements: Record<string, readonly string[]> = {},
): TargetCaseOption[] {
  return values.map((value) => ({
    value,
    label: formatCaseLabel(value),
    group,
    requiredModels: modelRequirements[value],
  }))
}

function modelCatalogCaseOptions(
  group: string,
  prefix: 'model_' | 'responses_model_',
  models: readonly string[],
): TargetCaseOption[] {
  return models.map((model) => {
    const value = modelCatalogCaseId(prefix, model)
    return {
      value,
      label: formatCaseLabel(value),
      group,
      requiredModels: [model],
    }
  })
}

function modelCatalogCaseId(prefix: 'model_' | 'responses_model_', model: string): string {
  return `${prefix}${model.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')}`
}

function betaCatalogCaseOptions(group: string, betas: readonly string[]): TargetCaseOption[] {
  return betas.map((beta) => ({
    value: `beta_catalog_${beta.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')}`,
    label: formatCaseLabel(`beta_catalog_${beta}`),
    group,
  }))
}

function formatCaseLabel(value: string): string {
  return value
    .replace(/[._-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function parseTargetCaseValue(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function serializeTargetCaseValue(values: string[]): string {
  return Array.from(new Set(values)).join(',')
}

function normalizeAgentTargetCases(agentProvider: AgentProvider, targetCases: string): string {
  const selected = parseTargetCaseValue(targetCases)
  if (agentProvider !== 'claude-agent' || selected.length === 0) {
    return targetCases
  }

  const looksLikeLegacyFullSelection =
    selected.length >= 9
    && selected.every((caseId) => LEGACY_CLAUDE_AGENT_SELECTED_CASES.has(caseId))

  return looksLikeLegacyFullSelection ? '' : targetCases
}

function selectedStandardOption(apiType: StandardApiType): StandardApiOption {
  return STANDARD_API_OPTIONS.find((option) => option.value === apiType) ?? STANDARD_API_OPTIONS[0]
}

function parsePositiveNumber(value: string, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function mergeRunSummaries(summaries: RunSummary[]): RunSummary {
  if (summaries.length === 0) {
    const now = new Date().toISOString()
    return { startedAt: now, finishedAt: now, providers: [], totalPassed: 0, totalFailed: 0, totalSkipped: 0 }
  }
  return {
    startedAt: summaries[0].startedAt,
    finishedAt: summaries[summaries.length - 1].finishedAt,
    providers: summaries.flatMap((s) => s.providers),
    totalPassed: summaries.reduce((sum, s) => sum + s.totalPassed, 0),
    totalFailed: summaries.reduce((sum, s) => sum + s.totalFailed, 0),
    totalSkipped: summaries.reduce((sum, s) => sum + s.totalSkipped, 0),
  }
}

function emptyToUndefined(value: string): string | undefined {
  const trimmed = value.trim()
  return trimmed ? trimmed : undefined
}

function matchesRequiredModel(option: TargetCaseOption, model: string): boolean {
  if (!option.requiredModels || option.requiredModels.length === 0) {
    return true
  }
  const normalizedModel = normalizeModelName(model)
  return option.requiredModels.some((requiredModel) => normalizeModelName(requiredModel) === normalizedModel)
}

function getTargetCaseOptions(apiType: StandardApiType, model: string): TargetCaseOption[] {
  const options = STANDARD_TARGET_CASES[apiType]
  const geminiCompatibility = isGeminiOpenAICompatibilityModel(model)
  return options.filter((option) => {
    if (!matchesRequiredModel(option, model)) {
      return false
    }
    if (apiType !== 'openai.chat') {
      return isCaseRecommendedForModel(apiType, option.value, model)
    }
    if (option.group === 'Gemini compatibility') {
      return geminiCompatibility
    }
    if (option.group === 'OpenAI-specific') {
      return !geminiCompatibility
    }
    return isCaseRecommendedForModel(apiType, option.value, model)
  })
}

const SITE_STORAGE_KEY = 'llm-spec-site-profiles'
const RUN_DRAFT_STORAGE_KEY = 'llm-spec-run-draft'
const LAST_SITE_NAME_STORAGE_KEY = 'llm-spec-last-site-name'
const LAST_SITE_CONFIG_STORAGE_KEY = 'llm-spec-last-site'
const ACTIVE_BACKEND_JOB_STORAGE_KEY = 'llm-spec-active-backend-job'
const LEGACY_PROFILE_STORAGE_KEY = 'llm-spec-profiles'
const LEGACY_LAST_PROFILE_STORAGE_KEY = 'llm-spec-last-profile'
const DEFAULT_R9S_MANAGER_BASE_URL = 'https://portal-api.r9s.ai'

interface SavedProfile {
  name: string
  savedAt: string
  config: SiteProfileConfig
  legacyDraft?: RunDraft
}

type PortableSiteProfileConfig = Omit<SiteProfileConfig, 'backendUrl'>

interface SitesExportPayload {
  kind: 'llm-spec-sites'
  version: 1
  exportedAt: string
  profiles: Array<Pick<SavedProfile, 'name' | 'savedAt'> & { config: PortableSiteProfileConfig }>
  selectedProfileName: string | null
  siteConfig: PortableSiteProfileConfig
  runDraft: RunDraft
}

interface NormalizedSitesImport {
  profiles: SavedProfile[]
  selectedProfileName: string | null
  siteConfig?: SiteProfileConfig
  runDraft?: RunDraft
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function stringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function booleanValue(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function normalizeStandardExecution(value: unknown): StandardExecutionMode {
  return value === 'backend' ? 'backend' : 'browser'
}

function isStandardApiType(value: unknown): value is StandardApiType {
  return STANDARD_API_OPTIONS.some((option) => option.value === value)
}

function isAgentProvider(value: unknown): value is AgentProvider {
  return AGENT_OPTIONS.some((option) => option.value === value)
}

function createTargetId(kind: RunTargetKind): string {
  return `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function createDefaultSiteConfig(): SiteProfileConfig {
  return {
    apiKey: '',
    apiBaseUrl: '',
    customHeaders: '{}',
    apiVersion: '',
    backendUrl: DEFAULT_BACKEND_URL,
    standardExecution: 'browser',
    workingDirectory: '',
    skipGitRepoCheck: true,
    testImagePath: '',
    r9sBillingAuditEnabled: false,
    r9sManagerBaseUrl: DEFAULT_R9S_MANAGER_BASE_URL,
    r9sManagerKey: '',
    r9sTokenId: '',
  }
}

function createDefaultRunSettings(): RunSettings {
  return {
    timeoutMs: '600000',
    concurrency: '1',
    failFast: false,
  }
}

function createStandardRunTarget(apiType: StandardApiType = 'openai.chat'): StandardRunTarget {
  const option = selectedStandardOption(apiType)
  return {
    id: createTargetId('standard'),
    kind: 'standard',
    enabled: true,
    apiType,
    model: option.defaultModel,
    targetCases: '',
  }
}

function createAgentRunTarget(agentProvider: AgentProvider = 'claude-agent'): AgentRunTarget {
  const option = AGENT_OPTIONS.find((item) => item.value === agentProvider) ?? AGENT_OPTIONS[0]
  return {
    id: createTargetId('agent'),
    kind: 'agent',
    enabled: true,
    agentProvider,
    model: option.defaultModel,
    targetCases: '',
  }
}

function createDefaultRunDraft(): RunDraft {
  return {
    targets: [createStandardRunTarget()],
    settings: createDefaultRunSettings(),
  }
}

function normalizeSiteConfig(value: unknown): SiteProfileConfig {
  const defaults = createDefaultSiteConfig()
  if (!isRecord(value)) {
    return defaults
  }

  return {
    apiKey: stringValue(value.apiKey, defaults.apiKey),
    apiBaseUrl: stringValue(value.apiBaseUrl, defaults.apiBaseUrl),
    customHeaders: stringValue(value.customHeaders, defaults.customHeaders),
    apiVersion: stringValue(value.apiVersion, defaults.apiVersion),
    backendUrl: defaults.backendUrl,
    standardExecution: normalizeStandardExecution(value.standardExecution),
    workingDirectory: stringValue(value.workingDirectory, defaults.workingDirectory),
    skipGitRepoCheck: booleanValue(value.skipGitRepoCheck, defaults.skipGitRepoCheck),
    testImagePath: stringValue(value.testImagePath, defaults.testImagePath),
    r9sBillingAuditEnabled: booleanValue(value.r9sBillingAuditEnabled, defaults.r9sBillingAuditEnabled),
    r9sManagerBaseUrl: stringValue(value.r9sManagerBaseUrl, defaults.r9sManagerBaseUrl),
    r9sManagerKey: stringValue(value.r9sManagerKey, defaults.r9sManagerKey),
    r9sTokenId: stringValue(value.r9sTokenId, defaults.r9sTokenId),
  }
}

function toPortableSiteConfig(config: SiteProfileConfig): PortableSiteProfileConfig {
  return {
    apiKey: config.apiKey,
    apiBaseUrl: config.apiBaseUrl,
    customHeaders: config.customHeaders,
    apiVersion: config.apiVersion,
    standardExecution: config.standardExecution,
    workingDirectory: config.workingDirectory,
    skipGitRepoCheck: config.skipGitRepoCheck,
    testImagePath: config.testImagePath,
    r9sBillingAuditEnabled: config.r9sBillingAuditEnabled,
    r9sManagerBaseUrl: config.r9sManagerBaseUrl,
    r9sManagerKey: config.r9sManagerKey,
    r9sTokenId: config.r9sTokenId,
  }
}

function toPortableProfile(profile: SavedProfile): Pick<SavedProfile, 'name' | 'savedAt'> & { config: PortableSiteProfileConfig } {
  return {
    name: profile.name,
    savedAt: profile.savedAt,
    config: toPortableSiteConfig(profile.config),
  }
}

function siteConfigsEqual(left: SiteProfileConfig, right: SiteProfileConfig): boolean {
  return JSON.stringify(toPortableSiteConfig(left)) === JSON.stringify(toPortableSiteConfig(right))
}

function createCopyProfileName(baseName: string, profiles: readonly SavedProfile[]): string {
  const existingNames = new Set(profiles.map((profile) => profile.name))
  const base = `${baseName || 'Environment'} copy`
  if (!existingNames.has(base)) {
    return base
  }

  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${base} ${index}`
    if (!existingNames.has(candidate)) {
      return candidate
    }
  }

  return `${base} ${Date.now()}`
}

function normalizeRunSettings(value: unknown): RunSettings {
  const defaults = createDefaultRunSettings()
  if (!isRecord(value)) {
    return defaults
  }

  return {
    timeoutMs: stringValue(value.timeoutMs, defaults.timeoutMs),
    concurrency: stringValue(value.concurrency, defaults.concurrency),
    failFast: false,
  }
}

function normalizeRunTarget(value: unknown): RunTarget | undefined {
  if (!isRecord(value)) {
    return undefined
  }

  const id = stringValue(value.id) || createTargetId(value.kind === 'agent' ? 'agent' : 'standard')
  const enabled = booleanValue(value.enabled, true)
  const targetCases = stringValue(value.targetCases)

  if (value.kind === 'agent') {
    const agentProvider = isAgentProvider(value.agentProvider) ? value.agentProvider : 'claude-agent'
    const option = AGENT_OPTIONS.find((item) => item.value === agentProvider) ?? AGENT_OPTIONS[0]
    const target: AgentRunTarget = {
      id,
      kind: 'agent',
      enabled,
      agentProvider,
      model: stringValue(value.model, option.defaultModel),
      targetCases,
    }
    return {
      ...target,
      targetCases: normalizeAgentTargetCases(agentProvider, pruneHiddenTargetCases(target)),
    }
  }

  const apiType = isStandardApiType(value.apiType) ? value.apiType : 'openai.chat'
  const option = selectedStandardOption(apiType)
  const target: StandardRunTarget = {
    id,
    kind: 'standard',
    enabled,
    apiType,
    model: stringValue(value.model, option.defaultModel),
    targetCases,
  }
  return {
    ...target,
    targetCases: pruneHiddenTargetCases(target),
  }
}

function normalizeRunDraft(value: unknown): RunDraft | undefined {
  if (!isRecord(value)) {
    return undefined
  }

  const targets = Array.isArray(value.targets)
    ? value.targets.map(normalizeRunTarget).filter((item): item is RunTarget => Boolean(item))
    : []

  return {
    targets: targets.length > 0 ? targets : [createStandardRunTarget()],
    settings: normalizeRunSettings(value.settings),
  }
}

function legacyRunDraftFromConfig(value: unknown): RunDraft {
  if (!isRecord(value)) {
    return createDefaultRunDraft()
  }

  const provider = stringValue(value.provider, 'openai.chat')
  const model = stringValue(value.model)
  const targetCases = stringValue(value.targetCases)
  const targets: RunTarget[] = []

  if (provider === 'all') {
    for (const option of STANDARD_API_OPTIONS) {
      targets.push({
        ...createStandardRunTarget(option.value),
        model: model || option.defaultModel,
        targetCases,
      })
    }
  } else if (isStandardApiType(provider)) {
    targets.push({
      ...createStandardRunTarget(provider),
      model: model || selectedStandardOption(provider).defaultModel,
      targetCases,
    })
  }

  const enabledAgents = Array.isArray(value.enabledAgents)
    ? value.enabledAgents.filter(isAgentProvider)
    : []
  for (const agentProvider of enabledAgents) {
    const option = AGENT_OPTIONS.find((item) => item.value === agentProvider) ?? AGENT_OPTIONS[0]
    targets.push({
      ...createAgentRunTarget(agentProvider),
      model: model || option.defaultModel,
      targetCases,
    })
  }

  return {
    targets: targets.length > 0 ? targets : [createStandardRunTarget()],
    settings: normalizeRunSettings(value),
  }
}

function normalizeProfile(value: unknown, legacy = false): SavedProfile | undefined {
  if (!isRecord(value) || typeof value.name !== 'string' || !value.name.trim()) {
    return undefined
  }

  return {
    name: value.name.trim(),
    savedAt: stringValue(value.savedAt, new Date().toISOString()),
    config: normalizeSiteConfig(value.config),
    legacyDraft: legacy ? legacyRunDraftFromConfig(value.config) : undefined,
  }
}

function readProfilesFromStorage(key: string, legacy = false): SavedProfile[] {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) {
      return []
    }
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.map((item) => normalizeProfile(item, legacy)).filter((item): item is SavedProfile => Boolean(item))
  } catch {
    return []
  }
}

function loadProfiles(): SavedProfile[] {
  const profiles = readProfilesFromStorage(SITE_STORAGE_KEY)
  return profiles.length > 0 ? profiles : readProfilesFromStorage(LEGACY_PROFILE_STORAGE_KEY, true)
}

function saveProfiles(profiles: SavedProfile[]): void {
  localStorage.setItem(
    SITE_STORAGE_KEY,
    JSON.stringify(profiles.map(toPortableProfile)),
  )
}

function normalizeProfileList(value: unknown): SavedProfile[] {
  if (!Array.isArray(value)) {
    return []
  }

  const profilesByName = new Map<string, SavedProfile>()
  for (const item of value) {
    const profile = normalizeProfile(item)
    if (profile) {
      profilesByName.set(profile.name, profile)
    }
  }
  return Array.from(profilesByName.values())
}

function normalizeSitesImportPayload(value: unknown): NormalizedSitesImport {
  if (Array.isArray(value)) {
    return {
      profiles: normalizeProfileList(value),
      selectedProfileName: null,
    }
  }

  if (!isRecord(value)) {
    throw new Error('Sites import must be a JSON object')
  }

  const profiles = normalizeProfileList(value.profiles)
  const selectedName = stringValue(value.selectedProfileName, stringValue(value.selectedName)).trim()
  const selectedProfileName = selectedName && profiles.some((profile) => profile.name === selectedName)
    ? selectedName
    : null
  const rawSiteConfig = value.siteConfig ?? value.currentSiteConfig
  const rawRunDraft = value.runDraft ?? value.currentRunDraft

  return {
    profiles,
    selectedProfileName,
    siteConfig: rawSiteConfig === undefined ? undefined : normalizeSiteConfig(rawSiteConfig),
    runDraft: rawRunDraft === undefined ? undefined : normalizeRunDraft(rawRunDraft),
  }
}

function loadSiteConfig(): SiteProfileConfig {
  try {
    const raw = localStorage.getItem(LAST_SITE_CONFIG_STORAGE_KEY)
    if (raw) {
      return normalizeSiteConfig(JSON.parse(raw) as unknown)
    }
  } catch {
    // Ignore malformed local storage and fall back to legacy/default values.
  }

  try {
    const raw = localStorage.getItem(LEGACY_LAST_PROFILE_STORAGE_KEY)
    if (raw) {
      return normalizeSiteConfig(JSON.parse(raw) as unknown)
    }
  } catch {
    // Ignore malformed legacy values.
  }

  return createDefaultSiteConfig()
}

function loadRunDraft(): RunDraft {
  try {
    const raw = localStorage.getItem(RUN_DRAFT_STORAGE_KEY)
    if (raw) {
      const draft = normalizeRunDraft(JSON.parse(raw) as unknown)
      if (draft) {
        return draft
      }
    }
  } catch {
    // Ignore malformed local storage and fall back to legacy/default values.
  }

  try {
    const raw = localStorage.getItem(LEGACY_LAST_PROFILE_STORAGE_KEY)
    if (raw) {
      return legacyRunDraftFromConfig(JSON.parse(raw) as unknown)
    }
  } catch {
    // Ignore malformed legacy values.
  }

  return createDefaultRunDraft()
}

function loadActiveBackendJob(): ActiveBackendJob | null {
  try {
    const raw = localStorage.getItem(ACTIVE_BACKEND_JOB_STORAGE_KEY)
    if (!raw) {
      return null
    }
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object') {
      return null
    }
    const value = parsed as { id?: unknown; backendUrl?: unknown }
    if (typeof value.id !== 'string' || typeof value.backendUrl !== 'string') {
      return null
    }
    const backendUrl = resolveRuntimeBackendUrl(value.backendUrl)
    if (import.meta.env.PROD && isLoopbackBackendUrl(value.backendUrl) && backendUrl !== value.backendUrl.trim()) {
      return null
    }
    return { id: value.id, backendUrl }
  } catch {
    return null
  }
}

function saveActiveBackendJob(job: ActiveBackendJob | null): void {
  if (!job) {
    localStorage.removeItem(ACTIVE_BACKEND_JOB_STORAGE_KEY)
    return
  }
  localStorage.setItem(ACTIVE_BACKEND_JOB_STORAGE_KEY, JSON.stringify(job))
}

function sanitizeDownloadNamePart(value: string, fallback: string): string {
  const normalized = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized || fallback
}

function downloadJsonFile(fileName: string, value: unknown): void {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function sanitizeRunSummaryForExport(summary: RunSummary): RunSummary {
  if (!summary.runSnapshot || !('backendUrl' in summary.runSnapshot)) {
    return summary
  }
  const runSnapshot = { ...summary.runSnapshot }
  delete runSnapshot.backendUrl
  return { ...summary, runSnapshot }
}

function parseCustomHeaders(value: string): Record<string, string> | undefined {
  const trimmed = value.trim()
  if (!trimmed || trimmed === '{}') {
    return undefined
  }

  const parsed = JSON.parse(trimmed) as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Custom headers must be a JSON object')
  }

  const headers: Record<string, string> = {}
  for (const [key, headerValue] of Object.entries(parsed)) {
    if (typeof headerValue !== 'string') {
      throw new Error('Custom header values must be strings')
    }
    const headerName = key.trim()
    if (!headerName) {
      if (headerValue.trim()) {
        throw new Error('Custom header names cannot be empty')
      }
      continue
    }
    if (headerValue.trim()) {
      headers[headerName] = headerValue
    }
  }
  return Object.keys(headers).length > 0 ? headers : undefined
}

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function Field(props: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  type?: string
  autoComplete?: string
  revealable?: boolean
}) {
  const [visible, setVisible] = useState(false)
  const isPassword = props.type === 'password'
  const inputType = isPassword && visible ? 'text' : (props.type ?? 'text')

  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-semibold text-slate-700">{props.label}</label>
      <div className="relative">
        <input
          className={cn(
            "block w-full rounded-lg border border-slate-200 bg-slate-50 py-2 px-3 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-slate-900 focus:bg-white transition-all placeholder:text-slate-400",
            isPassword && "pr-10",
          )}
          value={props.value}
          onChange={(event) => { props.onChange(event.target.value) }}
          placeholder={props.placeholder}
          type={inputType}
          autoComplete={props.autoComplete}
        />
        {isPassword && (
          <button
            type="button"
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-slate-600 transition-colors"
            onClick={() => { setVisible((v) => !v) }}
            tabIndex={-1}
            aria-label={visible ? 'Hide password' : 'Show password'}
          >
            {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
    </div>
  )
}

function StandardApiSelect(props: {
  value: StandardApiType
  onChange: (value: StandardApiType) => void
}) {
  return (
    <select
      className="block w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-sm text-slate-900 outline-none transition-shadow focus:ring-2 focus:ring-slate-900"
      value={props.value}
      onChange={(event) => { props.onChange(event.target.value as StandardApiType) }}
    >
      {STANDARD_API_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
  )
}

function AgentProviderSelect(props: {
  value: AgentProvider
  onChange: (value: AgentProvider) => void
}) {
  return (
    <select
      className="block w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-sm text-slate-900 outline-none transition-shadow focus:ring-2 focus:ring-slate-900"
      value={props.value}
      onChange={(event) => { props.onChange(event.target.value as AgentProvider) }}
    >
      {AGENT_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
  )
}

function TextAreaField(props: {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
  rows?: number
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-semibold text-slate-700">{props.label}</label>
      <textarea
        className="block w-full rounded-lg border border-slate-200 bg-slate-50 py-3 px-3 text-sm font-mono text-slate-900 outline-none focus:ring-2 focus:ring-slate-900 focus:bg-white transition-all placeholder:text-slate-400 resize-y"
        value={props.value}
        onChange={(event) => { props.onChange(event.target.value) }}
        placeholder={props.placeholder}
        rows={props.rows ?? 4}
      />
    </div>
  )
}

interface CustomHeaderRow {
  name: string
  value: string
}

function parseCustomHeaderRows(value: string): { rows: CustomHeaderRow[]; error?: string } {
  try {
    const headers = parseCustomHeaders(value) ?? {}
    return {
      rows: Object.entries(headers).map(([name, headerValue]) => ({ name, value: headerValue })),
    }
  } catch (error) {
    return { rows: [], error: formatUnknownError(error) }
  }
}

function serializeCustomHeaderRows(rows: CustomHeaderRow[]): string {
  const headers: Record<string, string> = {}
  for (const row of rows) {
    const name = row.name.trim()
    if (!name) {
      continue
    }
    headers[name] = row.value
  }
  return JSON.stringify(headers, null, 2)
}

function CustomHeadersField(props: {
  value: string
  onChange: (value: string) => void
}) {
  const { value, onChange } = props
  const parsed = useMemo(() => parseCustomHeaderRows(value), [value])
  const [rows, setRows] = useState<CustomHeaderRow[]>(parsed.rows)
  const [rawMode, setRawMode] = useState(false)
  const lastSerializedRef = useRef<string | null>(null)

  useEffect(() => {
    if (value === lastSerializedRef.current || parsed.error) {
      return
    }
    setRows(parsed.rows)
  }, [parsed.error, parsed.rows, value])

  const duplicateNames = useMemo(() => {
    const counts = new Map<string, number>()
    for (const row of rows) {
      const name = row.name.trim().toLowerCase()
      if (!name) {
        continue
      }
      counts.set(name, (counts.get(name) ?? 0) + 1)
    }
    return new Set(Array.from(counts.entries()).filter(([, count]) => count > 1).map(([name]) => name))
  }, [rows])

  const commitRows = useCallback((nextRows: CustomHeaderRow[]) => {
    setRows(nextRows)
    const serialized = serializeCustomHeaderRows(nextRows)
    lastSerializedRef.current = serialized
    onChange(serialized)
  }, [onChange])

  const updateRow = useCallback((index: number, patch: Partial<CustomHeaderRow>) => {
    commitRows(rows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row)))
  }, [commitRows, rows])

  const addRow = useCallback(() => {
    commitRows([...rows, { name: '', value: '' }])
    setRawMode(false)
  }, [commitRows, rows])

  const removeRow = useCallback((index: number) => {
    commitRows(rows.filter((_, rowIndex) => rowIndex !== index))
  }, [commitRows, rows])

  const showRaw = rawMode || Boolean(parsed.error)

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="block text-sm font-semibold text-slate-700">Custom Headers</label>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => { setRawMode((current) => !current && !parsed.error) }}
            disabled={Boolean(parsed.error)}
          >
            {showRaw ? 'Key/Value' : 'Raw JSON'}
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={addRow} disabled={Boolean(parsed.error)}>
            <Plus className="h-4 w-4" />
            Header
          </Button>
        </div>
      </div>

      {showRaw ? (
        <div className="space-y-2">
          <TextAreaField
            label="Custom Headers JSON"
            value={value}
            onChange={(value) => {
              lastSerializedRef.current = null
              onChange(value)
            }}
            placeholder='{"X-Debug-Channel-ID":"13"}'
          />
          {parsed.error && (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {parsed.error}
            </div>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {rows.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">
              No custom headers
            </div>
          ) : (
            rows.map((row, index) => {
              const normalizedName = row.name.trim().toLowerCase()
              const duplicate = normalizedName ? duplicateNames.has(normalizedName) : false
              const missingName = !row.name.trim() && row.value.trim()
              return (
                <div key={index} className="space-y-1.5 rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_2.5rem]">
                    <input
                      className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:ring-2 focus:ring-slate-900"
                      value={row.name}
                      onChange={(event) => { updateRow(index, { name: event.target.value }) }}
                      placeholder="Header name"
                      autoComplete="off"
                    />
                    <input
                      className="h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:ring-2 focus:ring-slate-900"
                      value={row.value}
                      onChange={(event) => { updateRow(index, { value: event.target.value }) }}
                      placeholder="Header value"
                      autoComplete="off"
                    />
                    <button
                      type="button"
                      className="flex h-10 w-full items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 md:w-10"
                      onClick={() => { removeRow(index) }}
                      aria-label="Remove header"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  {missingName && <div className="text-xs text-rose-600">Header name is required.</div>}
                  {duplicate && <div className="text-xs text-amber-700">Duplicate header names use the last value.</div>}
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}

function ToggleButton<TValue extends string>(props: {
  active: boolean
  value: TValue
  onSelect: (value: TValue) => void
  children: ReactNode
  size?: 'default' | 'sm'
}) {
  const sizeClasses = props.size === 'sm'
    ? 'px-3 py-1.5 text-xs font-semibold'
    : 'px-4 py-2 text-sm font-medium'
  return (
    <button
      type="button"
      className={`flex items-center ${sizeClasses} rounded-md transition-all ${
        props.active
          ? 'bg-slate-900 text-white shadow-md'
          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/50'
      }`}
      onClick={() => { props.onSelect(props.value) }}
    >
      {props.children}
    </button>
  )
}

function ConfigurationSelector(props: {
  profiles: SavedProfile[]
  selectedName: string | null
  hasUnsavedChanges: boolean
  onSelect: (profile: SavedProfile) => void
  onAdd: () => void
  onEdit: (profile: SavedProfile) => void
  onDuplicate: (profile: SavedProfile) => void
  onDelete: (name: string) => void
  onExport: (profile: SavedProfile) => void
}) {
  const { profiles, selectedName, hasUnsavedChanges, onSelect, onAdd, onEdit, onDuplicate, onDelete, onExport } = props
  const [open, setOpen] = useState(false)
  const selectedProfile = profiles.find((profile) => profile.name === selectedName)

  if (profiles.length === 0) {
    return (
      <Button type="button" onClick={onAdd} className="w-full sm:w-auto">
        <Plus className="w-4 h-4" />
        Add Environment
      </Button>
    )
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="h-10 min-w-0 flex-1 justify-between gap-3"
        >
          <span className="min-w-0 truncate text-left">
            {selectedProfile?.name
              ? `${selectedProfile.name}${hasUnsavedChanges ? ' *' : ''}`
              : 'Select environment'}
          </span>
          <ChevronsUpDown className="h-4 w-4 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(25rem,calc(100vw-2rem))] p-0">
        <div className="border-b border-slate-100 px-3 py-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Environments</span>
        </div>
        <ScrollArea className="max-h-72">
          <div className="p-1">
            {profiles.map((profile) => {
              const active = profile.name === selectedName
              return (
                <div
                  key={profile.name}
                  className={cn(
                    'group flex items-center gap-2 rounded-md px-2 py-2 hover:bg-slate-100',
                    active && 'bg-slate-100',
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => {
                      onSelect(profile)
                      setOpen(false)
                    }}
                  >
                    <span className="block truncate text-sm font-semibold text-slate-900">{profile.name}</span>
                    <span className="block truncate text-xs text-slate-500">
                      {profile.config.apiBaseUrl || 'Provider default'}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-900"
                    onClick={(event) => {
                      event.stopPropagation()
                      onExport(profile)
                    }}
                    aria-label={`Export ${profile.name}`}
                  >
                    <Download className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-900"
                    onClick={(event) => {
                      event.stopPropagation()
                      onDuplicate(profile)
                      setOpen(false)
                    }}
                    aria-label={`Duplicate ${profile.name}`}
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-900"
                    onClick={(event) => {
                      event.stopPropagation()
                      onEdit(profile)
                      setOpen(false)
                    }}
                    aria-label={`Edit ${profile.name}`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-500"
                    onClick={(event) => {
                      event.stopPropagation()
                      onDelete(profile.name)
                    }}
                    aria-label={`Delete ${profile.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )
            })}
          </div>
        </ScrollArea>
        <div className="border-t border-slate-100 p-2">
          <Button
            type="button"
            variant="ghost"
            className="w-full justify-start"
            onClick={() => {
              setOpen(false)
              onAdd()
            }}
          >
            <Plus className="w-4 h-4" />
            Add Environment
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}

function SummaryField(props: { label: string; value: ReactNode; muted?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold uppercase tracking-wide text-slate-400">{props.label}</dt>
      <dd className={cn('mt-1 truncate text-sm font-semibold text-slate-800', props.muted && 'text-slate-400')}>
        {props.value}
      </dd>
    </div>
  )
}

function TargetCasesField(props: {
  label?: string
  value: string
  options: TargetCaseOption[]
  onChange: (value: string) => void
  modelQuickSelect?: {
    apiType: StandardApiType
    currentModel: string
    models: readonly string[]
    allOptions: TargetCaseOption[]
    onSelectModelCases?: (model: string, targetCases: string) => void
  }
  agentToggles?: Array<{
    label: string
    enabled: boolean
    onToggle: () => void
  }>
}) {
  const { label, value, options, onChange, modelQuickSelect, agentToggles } = props
  const enabledAgentLabels = agentToggles?.filter((a) => a.enabled) ?? []
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [quickModel, setQuickModel] = useState('')
  const quickSelectApiType = modelQuickSelect?.apiType
  const quickSelectCurrentModel = modelQuickSelect?.currentModel ?? ''
  const selectedValues = useMemo(() => parseTargetCaseValue(value), [value])
  const selectedSet = useMemo(() => new Set(selectedValues), [selectedValues])
  const normalizedSearch = search.trim().toLowerCase()
  const filteredOptions = useMemo(
    () => options.filter((option) => {
      if (!normalizedSearch) {
        return true
      }
      return (
        option.value.toLowerCase().includes(normalizedSearch)
        || option.label.toLowerCase().includes(normalizedSearch)
        || option.group.toLowerCase().includes(normalizedSearch)
      )
    }),
    [normalizedSearch, options],
  )
  const customValue = search.trim()
  const canAddCustom =
    customValue.length > 0
    && !options.some((option) => option.value === customValue)
    && !selectedSet.has(customValue)
  const quickModels = useMemo(() => {
    if (!modelQuickSelect) {
      return []
    }
    return Array.from(
      new Set([modelQuickSelect.currentModel, ...modelQuickSelect.models].map((model) => model.trim()).filter(Boolean)),
    )
  }, [modelQuickSelect])

  useEffect(() => {
    setQuickModel('')
  }, [quickSelectApiType, quickSelectCurrentModel])

  const getQuickModelCases = useCallback((model: string): TargetCaseOption[] => {
    if (!modelQuickSelect || !model.trim()) {
      return []
    }

    const normalizedModel = normalizeModelName(model)
    const catalogOptions = modelQuickSelect.allOptions.filter((option) =>
      option.requiredModels?.some((requiredModel) =>
        normalizeModelName(requiredModel) === normalizedModel,
      ),
    )
    const targetOptions = getTargetCaseOptions(modelQuickSelect.apiType, model)
    if (catalogOptions.length === 0) {
      return targetOptions
    }

    const targetValues = new Set(targetOptions.map((option) => option.value))
    return [
      ...targetOptions,
      ...catalogOptions.filter((option) => !targetValues.has(option.value)),
    ]
  }, [modelQuickSelect])

  const quickModelCaseCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const model of quickModels) {
      counts.set(model, new Set(getQuickModelCases(model).map((option) => option.value)).size)
    }
    return counts
  }, [getQuickModelCases, quickModels])

  const updateValues = useCallback((nextValues: string[]) => {
    onChange(serializeTargetCaseValue(nextValues))
  }, [onChange])

  const toggleValue = useCallback((value: string) => {
    setQuickModel('')
    if (selectedSet.has(value)) {
      updateValues(selectedValues.filter((item) => item !== value))
      return
    }
    updateValues([...selectedValues, value])
  }, [selectedSet, selectedValues, updateValues])

  const selectVisible = useCallback(() => {
    setQuickModel('')
    updateValues([...selectedValues, ...filteredOptions.map((option) => option.value)])
  }, [filteredOptions, selectedValues, updateValues])

  const selectQuickModelCases = useCallback((model: string) => {
    const caseFilter = serializeTargetCaseValue(getQuickModelCases(model).map((option) => option.value))
    setQuickModel(model)
    if (modelQuickSelect?.onSelectModelCases) {
      modelQuickSelect.onSelectModelCases(model, caseFilter)
      return
    }
    onChange(caseFilter)
  }, [getQuickModelCases, modelQuickSelect, onChange])

  const removeValue = useCallback((value: string) => {
    setQuickModel('')
    updateValues(selectedValues.filter((item) => item !== value))
  }, [selectedValues, updateValues])

  const selectedSummary = (() => {
    const parts: string[] = []
    if (enabledAgentLabels.length > 0) {
      parts.push(`${enabledAgentLabels.length} agent${enabledAgentLabels.length > 1 ? 's' : ''}`)
    }
    if (selectedValues.length === 0) {
      parts.push('All cases')
    } else {
      parts.push(`${selectedValues.length} selected`)
    }
    return parts.join(' + ')
  })()

  return (
    <div className="space-y-1.5">
      {label && <span className="block text-sm font-semibold text-slate-700">{label}</span>}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            role="combobox"
            aria-expanded={open}
            aria-label={label ?? 'Target cases'}
            className="h-10 w-full justify-between px-3 font-normal"
          >
            <span className={cn("truncate", selectedValues.length === 0 && "text-slate-500")}>
              {selectedSummary}
            </span>
            <ChevronsUpDown className="h-4 w-4 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[min(560px,calc(100vw-3rem))] p-0">
          <div className="flex items-center border-b border-slate-200 px-3">
            <Search className="mr-2 h-4 w-4 shrink-0 text-slate-400" />
            <input
              className="h-10 w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
              value={search}
              onChange={(event) => { setSearch(event.target.value) }}
              placeholder="Search cases or type custom filter"
            />
          </div>
          {modelQuickSelect && quickModels.length > 0 && (
            <div className="border-b border-slate-100 px-3 py-2">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Model quick select</span>
                {quickModel && <span className="truncate text-xs text-slate-400">{quickModel}</span>}
              </div>
              <div className="flex max-h-24 flex-wrap gap-1.5 overflow-auto pr-1">
                {quickModels.map((model) => {
                  const caseCount = quickModelCaseCounts.get(model) ?? 0
                  const active = normalizeModelName(quickModel || quickSelectCurrentModel) === normalizeModelName(model)
                  return (
                    <button
                      key={model}
                      type="button"
                      className={cn(
                        'max-w-full rounded-md border px-2 py-1 text-left text-xs transition-colors',
                        active
                          ? 'border-slate-900 bg-slate-900 text-white'
                          : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300 hover:bg-white hover:text-slate-900',
                        caseCount === 0 && 'cursor-not-allowed opacity-50',
                      )}
                      title={`Select cases for ${model}`}
                      onClick={() => { selectQuickModelCases(model) }}
                      disabled={caseCount === 0}
                    >
                      <span className="inline-block max-w-[13rem] truncate align-bottom">{model}</span>
                      <span className={cn('ml-1', active ? 'text-slate-200' : 'text-slate-400')}>({caseCount})</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2">
            <span className="text-xs text-slate-500">
              {selectedValues.length === 0 ? 'No filter selected' : `${selectedValues.length} case filters`}
            </span>
            <div className="flex gap-2">
              <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={selectVisible}>
                Select visible
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => {
                  setQuickModel('')
                  updateValues([])
                }}
              >
                Clear
              </Button>
            </div>
          </div>
          <ScrollArea className="h-72">
            <div className="p-1">
              {agentToggles && agentToggles.length > 0 && (
                <>
                  {agentToggles.map((agent) => (
                    <div
                      key={agent.label}
                      role="button"
                      tabIndex={0}
                      className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm hover:bg-slate-100"
                      onClick={agent.onToggle}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          agent.onToggle()
                        }
                      }}
                    >
                      <Checkbox
                        checked={agent.enabled}
                        onCheckedChange={agent.onToggle}
                        onClick={(event) => { event.stopPropagation() }}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-slate-900">{agent.label}</span>
                        <span className="block truncate text-xs text-slate-500">Agent</span>
                      </span>
                      <Bot className="w-4 h-4 text-slate-400 shrink-0" />
                    </div>
                  ))}
                  <div className="my-1 mx-2 border-t border-slate-200" />
                </>
              )}
              {filteredOptions.map((option) => {
                const checked = selectedSet.has(option.value)
                return (
                  <div
                    key={`${option.group}:${option.value}`}
                    role="button"
                    tabIndex={0}
                    className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm hover:bg-slate-100"
                    onClick={() => { toggleValue(option.value) }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        toggleValue(option.value)
                      }
                    }}
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={() => { toggleValue(option.value) }}
                      onClick={(event) => { event.stopPropagation() }}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-slate-900">{option.value}</span>
                      <span className="block truncate text-xs text-slate-500">{option.group} · {option.label}</span>
                    </span>
                  </div>
                )
              })}

              {filteredOptions.length === 0 && !canAddCustom && (
                <div className="px-3 py-8 text-center text-sm text-slate-500">
                  No cases found
                </div>
              )}

              {canAddCustom && (
                <button
                  type="button"
                  className="mt-1 flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm hover:bg-slate-100"
                  onClick={() => {
                    setQuickModel('')
                    updateValues([...selectedValues, customValue])
                    setSearch('')
                  }}
                >
                  <span className="flex h-4 w-4 items-center justify-center rounded-sm border border-slate-300">
                    <Check className="h-3 w-3" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-slate-900">Add custom filter</span>
                    <span className="block truncate font-mono text-xs text-slate-500">{customValue}</span>
                  </span>
                </button>
              )}
            </div>
          </ScrollArea>
        </PopoverContent>
      </Popover>

      {(selectedValues.length > 0 || enabledAgentLabels.length > 0) && (
        <div className="flex max-h-20 flex-wrap gap-1 overflow-auto rounded-md border border-slate-100 bg-slate-50 p-1.5">
          {enabledAgentLabels.map((agent) => (
            <Badge key={agent.label} variant="secondary" className="max-w-full gap-1 rounded-md pl-2 pr-1">
              <Bot className="w-3 h-3 text-slate-500" />
              <span className="truncate">{agent.label}</span>
              <button
                type="button"
                className="rounded-sm p-0.5 text-slate-500 hover:bg-slate-200 hover:text-slate-900"
                onClick={agent.onToggle}
                aria-label={`Disable ${agent.label}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
          {selectedValues.map((value) => (
            <Badge key={value} variant="secondary" className="max-w-full gap-1 rounded-md pl-2 pr-1 font-mono font-normal">
              <span className="truncate">{value}</span>
              <button
                type="button"
                className="rounded-sm p-0.5 text-slate-500 hover:bg-slate-200 hover:text-slate-900"
                onClick={() => { removeValue(value) }}
                aria-label={`Remove ${value}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  )
}

function getAgentOption(provider: AgentProvider): AgentOption {
  return AGENT_OPTIONS.find((option) => option.value === provider) ?? AGENT_OPTIONS[0]
}

function getRunTargetLabel(target: RunTarget): string {
  if (target.kind === 'agent') {
    return getAgentOption(target.agentProvider).label
  }
  return selectedStandardOption(target.apiType).label
}

function getRunTargetModel(target: RunTarget): string {
  if (target.kind === 'agent') {
    return target.model.trim() || getAgentOption(target.agentProvider).defaultModel
  }
  return target.model.trim() || selectedStandardOption(target.apiType).defaultModel
}

function getRunTargetModelLabel(target: RunTarget): string {
  return getRunTargetModel(target) || 'Default'
}

function getAllRunTargetCaseOptions(target: RunTarget): TargetCaseOption[] {
  if (target.kind === 'agent') {
    return AGENT_TARGET_CASES[target.agentProvider]
  }
  return STANDARD_TARGET_CASES[target.apiType]
}

function getCaseQuickSelectModels(target: StandardRunTarget): readonly string[] {
  const defaultModel = selectedStandardOption(target.apiType).defaultModel
  if (target.apiType === 'openai.chat') {
    return [defaultModel, ...OPENAI_CHAT_SERVED_MODEL_IDS]
  }
  if (target.apiType === 'openai.responses') {
    return [defaultModel, ...OPENAI_RESPONSES_SERVED_MODEL_IDS]
  }
  if (target.apiType === 'anthropic.messages') {
    return [defaultModel, ...ANTHROPIC_MESSAGES_MODEL_IDS]
  }
  return [defaultModel, ...GEMINI_GENERATE_CONTENT_SERVED_MODEL_IDS]
}

function getRunTargetCaseOptions(target: RunTarget): TargetCaseOption[] {
  if (target.kind === 'agent') {
    const model = getRunTargetModel(target)
    return AGENT_TARGET_CASES[target.agentProvider].filter((option) => matchesRequiredModel(option, model))
  }
  return getTargetCaseOptions(target.apiType, getRunTargetModel(target))
}

function pruneHiddenTargetCases(target: RunTarget): string {
  const selected = parseTargetCaseValue(target.targetCases)
  if (selected.length === 0) {
    return target.targetCases
  }

  const knownOptions = new Set(getAllRunTargetCaseOptions(target).map((option) => option.value))
  const visibleOptions = new Set(getRunTargetCaseOptions(target).map((option) => option.value))
  return serializeTargetCaseValue(selected.filter((caseId) => !knownOptions.has(caseId) || visibleOptions.has(caseId)))
}

function failedRunSummary(provider: string, model: string, error: unknown): RunSummary {
  const now = new Date().toISOString()
  return {
    startedAt: now,
    finishedAt: now,
    providers: [{
      provider,
      model,
      startedAt: now,
      finishedAt: now,
      passed: 0,
      failed: 1,
      skipped: 0,
      caseResults: [{
        id: 'run_error',
        description: `Failed to run ${provider}`,
        status: 'failed',
        durationMs: 0,
        coveredParams: [],
        error: error instanceof Error ? error.message : String(error),
      }],
      allParams: [],
      coveredParams: [],
      untestedParams: [],
    }],
    totalPassed: 0,
    totalFailed: 1,
    totalSkipped: 0,
  }
}

function effectiveStandardExecution(site: SiteProfileConfig): StandardExecutionMode {
  return site.r9sBillingAuditEnabled ? 'backend' : site.standardExecution
}

function buildBillingAuditConfig(site: SiteProfileConfig): R9SBillingAuditConfig | undefined {
  if (!site.r9sBillingAuditEnabled) {
    return undefined
  }
  return {
    enabled: true,
    managerBaseUrl: emptyToUndefined(site.r9sManagerBaseUrl) ?? DEFAULT_R9S_MANAGER_BASE_URL,
    managerKey: emptyToUndefined(site.r9sManagerKey),
    apiKey: emptyToUndefined(site.apiKey),
    tokenId: emptyToUndefined(site.r9sTokenId),
  }
}

function buildRunSnapshot(
  siteName: string | null,
  site: SiteProfileConfig,
  draft: RunDraft,
): RunSnapshot {
  const standardExecution = effectiveStandardExecution(site)
  return {
    siteName: siteName ?? undefined,
    apiBaseUrl: emptyToUndefined(site.apiBaseUrl),
    standardExecution,
    timeoutMs: parsePositiveNumber(draft.settings.timeoutMs, 45_000),
    concurrency: parsePositiveNumber(draft.settings.concurrency, 1),
    failFast: false,
    targets: draft.targets.map((target) => ({
      kind: target.kind,
      enabled: target.enabled,
      apiType: target.kind === 'standard' ? target.apiType : undefined,
      agentProvider: target.kind === 'agent' ? target.agentProvider : undefined,
      model: emptyToUndefined(getRunTargetModel(target)),
      targetCases: emptyToUndefined(target.targetCases),
      execution: target.kind === 'agent' ? 'backend' : standardExecution,
    })),
  }
}

function buildBackendJobRequest(
  siteName: string | null,
  site: SiteProfileConfig,
  activeTargets: RunTarget[],
  headers: Record<string, string> | undefined,
  timeoutMs: number,
  concurrency: number,
  runSnapshot: RunSnapshot,
): BackendJobRequest {
  return {
    apiKey: emptyToUndefined(site.apiKey),
    apiBaseUrl: emptyToUndefined(site.apiBaseUrl),
    standardExecution: effectiveStandardExecution(site),
    timeoutMs,
    concurrency,
    failFast: runSnapshot.failFast,
    customHeaders: headers,
    apiVersion: emptyToUndefined(site.apiVersion),
    workingDirectory: emptyToUndefined(site.workingDirectory),
    skipGitRepoCheck: site.skipGitRepoCheck,
    testImagePath: emptyToUndefined(site.testImagePath),
    billingAudit: buildBillingAuditConfig(site),
    persistResult: true,
    runSnapshot: {
      ...runSnapshot,
      siteName: siteName ?? undefined,
    },
    targets: activeTargets.map((target) => ({
      id: target.id,
      kind: target.kind,
      enabled: target.enabled,
      apiType: target.kind === 'standard' ? target.apiType : undefined,
      agentProvider: target.kind === 'agent' ? target.agentProvider : undefined,
      model: emptyToUndefined(getRunTargetModel(target)),
      targetCases: emptyToUndefined(target.targetCases),
    })),
  }
}

function formatHistoryTitle(entry: BackendRunHistoryEntry): string {
  if (entry.siteName) {
    return entry.siteName
  }
  if (entry.providers.length > 0) {
    return Array.from(new Set(entry.providers)).join(', ')
  }
  return 'Backend run'
}

function formatHistorySubtitle(entry: BackendRunHistoryEntry): string {
  const providerText = entry.providerCount === 1 ? '1 provider' : `${entry.providerCount} providers`
  const modelText = Array.from(new Set(entry.models)).slice(0, 2).join(', ')
  return modelText ? `${providerText} · ${modelText}` : providerText
}

function formatHistoryOutcome(entry: BackendRunHistoryEntry): string {
  return `${entry.totalPassed} passed / ${entry.totalFailed} failed / ${entry.totalSkipped} skipped`
}

type TargetProgressStatus = 'pending' | 'running' | 'complete'

interface TargetProgressState {
  id: string
  label: string
  status: TargetProgressStatus
  completed: number
  total: number
  passed: number
  failed: number
  skipped: number
  currentCase?: string
}

interface RunProgressState {
  completed: number
  total: number
  percent: number
  statusText: string
  detailText: string
  passed: number
  failed: number
  skipped: number
}

const EMPTY_RUN_PROGRESS: RunProgressState = {
  completed: 0,
  total: 0,
  percent: 0,
  statusText: 'Ready',
  detailText: 'No test run started',
  passed: 0,
  failed: 0,
  skipped: 0,
}

function createTargetProgress(target: RunTarget): TargetProgressState {
  return {
    id: target.id,
    label: getRunTargetLabel(target),
    status: 'pending',
    completed: 0,
    total: 1,
    passed: 0,
    failed: 0,
    skipped: 0,
  }
}

function summarizeProgress(targets: readonly TargetProgressState[]): RunProgressState {
  if (targets.length === 0) {
    return EMPTY_RUN_PROGRESS
  }

  const total = targets.reduce((sum, target) => sum + Math.max(target.total, 1), 0)
  const completed = targets.reduce((sum, target) => sum + Math.min(target.completed, Math.max(target.total, 1)), 0)
  const passed = targets.reduce((sum, target) => sum + target.passed, 0)
  const failed = targets.reduce((sum, target) => sum + target.failed, 0)
  const skipped = targets.reduce((sum, target) => sum + target.skipped, 0)
  const runningTarget = targets.find((target) => target.status === 'running')
  const pendingTarget = targets.find((target) => target.status === 'pending')
  const activeTarget = runningTarget ?? pendingTarget ?? targets[targets.length - 1]
  const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0
  const statusText = runningTarget
    ? `Running ${runningTarget.label}`
    : pendingTarget
      ? `Queued ${pendingTarget.label}`
      : 'Run complete'
  const caseDetail = activeTarget?.currentCase ? ` - ${activeTarget.currentCase}` : ''
  const detailText = `${completed}/${total} cases${caseDetail}`

  return {
    completed,
    total,
    percent,
    statusText,
    detailText,
    passed,
    failed,
    skipped,
  }
}

function isBackendJobTerminal(job: BackendJobStatusResponse): boolean {
  return job.status === 'completed' || job.status === 'failed'
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export function PlatformConsole({ onReport, onLoadFile, onLoadSample, loading, error }: PlatformConsoleProps) {
  const [profiles, setProfiles] = useState<SavedProfile[]>(() => loadProfiles())
  const [profileName, setProfileName] = useState('')
  const [selectedProfileName, setSelectedProfileName] = useState<string | null>(() => {
    const savedName = localStorage.getItem(LAST_SITE_NAME_STORAGE_KEY)
    return savedName || localStorage.getItem('llm-spec-last-profile-name') || null
  })
  const [siteConfig, setSiteConfig] = useState<SiteProfileConfig>(() => loadSiteConfig())
  const [runDraft, setRunDraft] = useState<RunDraft>(() => loadRunDraft())
  const [configDialogOpen, setConfigDialogOpen] = useState(false)
  const [editingProfileName, setEditingProfileName] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [runProgress, setRunProgress] = useState<RunProgressState>(EMPTY_RUN_PROGRESS)
  const [activeBackendJob, setActiveBackendJob] = useState<ActiveBackendJob | null>(() => loadActiveBackendJob())
  const [localError, setLocalError] = useState<string | null>(null)
  const [backendStatus, setBackendStatus] = useState<string | null>(null)
  const [historyItems, setHistoryItems] = useState<BackendRunHistoryEntry[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [runConsoleHeight, setRunConsoleHeight] = useState<number | null>(null)
  const runConsoleRef = useRef<HTMLDivElement | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const siteImportInputRef = useRef<HTMLInputElement | null>(null)
  const initialProfileLoadedRef = useRef(false)
  const backendJobPollingRef = useRef<string | null>(null)

  useEffect(() => {
    const element = runConsoleRef.current
    if (!element) {
      return undefined
    }

    const updateHeight = () => {
      setRunConsoleHeight(Math.ceil(element.getBoundingClientRect().height))
    }

    updateHeight()
    window.addEventListener('resize', updateHeight)

    if (typeof ResizeObserver === 'undefined') {
      return () => {
        window.removeEventListener('resize', updateHeight)
      }
    }

    const observer = new ResizeObserver(updateHeight)
    observer.observe(element)

    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateHeight)
    }
  }, [])

  useEffect(() => {
    if (initialProfileLoadedRef.current) {
      return
    }
    initialProfileLoadedRef.current = true
    const selected = selectedProfileName
      ? profiles.find((profile) => profile.name === selectedProfileName)
      : undefined
    if (!selected) {
      return
    }
    setSiteConfig(selected.config)
    setProfileName(selected.name)
    if (selected.legacyDraft) {
      setRunDraft(selected.legacyDraft)
    }
  }, [profiles, selectedProfileName])

  useEffect(() => {
    localStorage.setItem(RUN_DRAFT_STORAGE_KEY, JSON.stringify(runDraft))
  }, [runDraft])

  useEffect(() => {
    localStorage.setItem(LAST_SITE_CONFIG_STORAGE_KEY, JSON.stringify(toPortableSiteConfig(siteConfig)))
  }, [siteConfig])

  useEffect(() => {
    if (selectedProfileName) {
      localStorage.setItem(LAST_SITE_NAME_STORAGE_KEY, selectedProfileName)
    } else {
      localStorage.removeItem(LAST_SITE_NAME_STORAGE_KEY)
    }
  }, [selectedProfileName])

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.name === selectedProfileName),
    [profiles, selectedProfileName],
  )
  const hasUnsavedEnvironmentChanges = useMemo(
    () => selectedProfile ? !siteConfigsEqual(selectedProfile.config, siteConfig) : false,
    [selectedProfile, siteConfig],
  )
  const activeTargets = useMemo(
    () => runDraft.targets.filter((target) => target.enabled),
    [runDraft.targets],
  )
  const agentTargetCount = activeTargets.filter((target) => target.kind === 'agent').length
  const effectiveExecution = effectiveStandardExecution(siteConfig)
  const requiresBackend = effectiveExecution === 'backend' || agentTargetCount > 0
  const executionSummary = (() => {
    if (siteConfig.r9sBillingAuditEnabled) {
      return 'Backend service + R9S audit'
    }
    if (effectiveExecution === 'backend') {
      return 'Backend service'
    }
    if (agentTargetCount > 0) {
      return 'Browser + backend agents'
    }
    return 'Browser fetch'
  })()
  const customHeaderCount = useMemo(() => {
    try {
      return Object.keys(parseCustomHeaders(siteConfig.customHeaders) ?? {}).length
    } catch {
      return null
    }
  }, [siteConfig.customHeaders])
  const displayError = localError ?? error
  const hasRunProgress = runProgress.total > 0
  const progressStatusText = running || hasRunProgress ? runProgress.statusText : 'Ready'
  const progressDotColor = running
    ? 'bg-blue-500'
    : hasRunProgress && runProgress.failed > 0
      ? 'bg-rose-500'
      : 'bg-emerald-500'
  const progressBarColor = running
    ? 'bg-blue-500'
    : hasRunProgress && runProgress.failed > 0
      ? 'bg-rose-500'
      : 'bg-emerald-500'
  const progressTextColor = running
    ? 'text-blue-700'
    : hasRunProgress && runProgress.failed > 0
      ? 'text-rose-700'
      : 'text-slate-600'

  const updateSiteConfig = useCallback((patch: Partial<SiteProfileConfig>) => {
    setSiteConfig((current) => ({ ...current, ...patch }))
  }, [])

  const updateRunSettings = useCallback((patch: Partial<RunSettings>) => {
    setRunDraft((current) => ({
      ...current,
      settings: { ...current.settings, ...patch },
    }))
  }, [])

  const updateTarget = useCallback((id: string, updater: (target: RunTarget) => RunTarget) => {
    setRunDraft((current) => ({
      ...current,
      targets: current.targets.map((target) => target.id === id ? updater(target) : target),
    }))
  }, [])

  const handleTargetKindChange = useCallback((target: RunTarget, kind: RunTargetKind) => {
    updateTarget(target.id, () => {
      const nextTarget = kind === 'standard' ? createStandardRunTarget() : createAgentRunTarget()
      return {
        ...nextTarget,
        id: target.id,
        enabled: target.enabled,
      }
    })
  }, [updateTarget])

  const handleStandardApiChange = useCallback((target: RunTarget, apiType: StandardApiType) => {
    updateTarget(target.id, (current) => {
      if (current.kind !== 'standard') {
        return current
      }
      return {
        ...current,
        apiType,
        model: selectedStandardOption(apiType).defaultModel,
        targetCases: '',
      }
    })
  }, [updateTarget])

  const handleAgentProviderChange = useCallback((target: RunTarget, agentProvider: AgentProvider) => {
    updateTarget(target.id, (current) => {
      if (current.kind !== 'agent') {
        return current
      }
      return {
        ...current,
        agentProvider,
        model: getAgentOption(agentProvider).defaultModel,
        targetCases: '',
      }
    })
  }, [updateTarget])

  const handleAddStandardTarget = useCallback(() => {
    setRunDraft((current) => ({
      ...current,
      targets: [...current.targets, createStandardRunTarget()],
    }))
  }, [])

  const handleAddAgentTarget = useCallback(() => {
    setRunDraft((current) => ({
      ...current,
      targets: [...current.targets, createAgentRunTarget()],
    }))
  }, [])

  const handleRemoveTarget = useCallback((id: string) => {
    setRunDraft((current) => ({
      ...current,
      targets: current.targets.filter((target) => target.id !== id),
    }))
  }, [])

  const handleSaveProfile = useCallback(() => {
    const name = profileName.trim()
    if (!name) {
      return
    }

    const replacedNames = new Set([name])
    if (editingProfileName) {
      replacedNames.add(editingProfileName)
    }

    const updated = profiles.filter((profile) => !replacedNames.has(profile.name))
    updated.push({
      name,
      savedAt: new Date().toISOString(),
      config: siteConfig,
    })
    saveProfiles(updated)
    setProfiles(updated)
    setSelectedProfileName(name)
    setProfileName(name)
    setConfigDialogOpen(false)
    setEditingProfileName(null)
  }, [editingProfileName, profileName, profiles, siteConfig])

  const handleLoadProfile = useCallback((profile: SavedProfile) => {
    if (
      selectedProfileName
      && selectedProfileName !== profile.name
      && hasUnsavedEnvironmentChanges
      && !window.confirm('Discard unsaved environment changes and switch?')
    ) {
      return
    }

    setSiteConfig(profile.config)
    if (profile.legacyDraft) {
      setRunDraft(profile.legacyDraft)
    }
    setSelectedProfileName(profile.name)
    setProfileName(profile.name)
    setLocalError(null)
    setBackendStatus(null)
  }, [hasUnsavedEnvironmentChanges, selectedProfileName])

  const handleEditProfile = useCallback((profile: SavedProfile) => {
    if (
      selectedProfileName
      && selectedProfileName !== profile.name
      && hasUnsavedEnvironmentChanges
      && !window.confirm('Discard unsaved environment changes and edit another environment?')
    ) {
      return
    }

    setSiteConfig(profile.config)
    if (profile.legacyDraft) {
      setRunDraft(profile.legacyDraft)
    }
    setSelectedProfileName(profile.name)
    setProfileName(profile.name)
    setEditingProfileName(profile.name)
    setLocalError(null)
    setBackendStatus(null)
    setConfigDialogOpen(true)
  }, [hasUnsavedEnvironmentChanges, selectedProfileName])

  const handleDeleteProfile = useCallback((name: string) => {
    if (!window.confirm(`Delete environment "${name}"?`)) {
      return
    }

    const updated = profiles.filter((profile) => profile.name !== name)
    saveProfiles(updated)
    setProfiles(updated)
    if (selectedProfileName === name) {
      setSelectedProfileName(null)
    }
    if (profileName === name) {
      setProfileName('')
    }
    if (editingProfileName === name) {
      setEditingProfileName(null)
    }
  }, [editingProfileName, profileName, profiles, selectedProfileName])

  const handleDuplicateProfile = useCallback((profile: SavedProfile) => {
    if (
      selectedProfileName
      && selectedProfileName !== profile.name
      && hasUnsavedEnvironmentChanges
      && !window.confirm('Discard unsaved environment changes and duplicate another environment?')
    ) {
      return
    }

    setSiteConfig({ ...(profile.name === selectedProfileName ? siteConfig : profile.config) })
    if (profile.legacyDraft) {
      setRunDraft(profile.legacyDraft)
    }
    setSelectedProfileName(null)
    setProfileName(createCopyProfileName(profile.name, profiles))
    setEditingProfileName(null)
    setLocalError(null)
    setBackendStatus(null)
    setConfigDialogOpen(true)
  }, [hasUnsavedEnvironmentChanges, profiles, selectedProfileName, siteConfig])

  const handleExportSites = useCallback(() => {
    const payload: SitesExportPayload = {
      kind: 'llm-spec-sites',
      version: 1,
      exportedAt: new Date().toISOString(),
      profiles: profiles.map(toPortableProfile),
      selectedProfileName,
      siteConfig: toPortableSiteConfig(siteConfig),
      runDraft,
    }
    downloadJsonFile(`llm-spec-sites-${new Date().toISOString().slice(0, 10)}.json`, payload)
  }, [profiles, runDraft, selectedProfileName, siteConfig])

  const handleExportSite = useCallback((profile: SavedProfile) => {
    const payload: SitesExportPayload = {
      kind: 'llm-spec-sites',
      version: 1,
      exportedAt: new Date().toISOString(),
      profiles: [toPortableProfile(profile)],
      selectedProfileName: profile.name,
      siteConfig: toPortableSiteConfig(profile.config),
      runDraft,
    }
    downloadJsonFile(`llm-spec-site-${sanitizeDownloadNamePart(profile.name, 'site')}.json`, payload)
  }, [runDraft])

  const handleImportSitesFile = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    try {
      const payload = normalizeSitesImportPayload(JSON.parse(await file.text()) as unknown)
      if (payload.profiles.length === 0 && !payload.siteConfig) {
        throw new Error('Sites import contains no profiles or site config')
      }

      const nextSelectedName = payload.selectedProfileName ?? (payload.siteConfig ? null : payload.profiles[0]?.name ?? null)
      const nextSelectedProfile = nextSelectedName
        ? payload.profiles.find((profile) => profile.name === nextSelectedName)
        : undefined

      saveProfiles(payload.profiles)
      setProfiles(payload.profiles)
      setSelectedProfileName(nextSelectedName)
      setProfileName(nextSelectedName ?? '')
      setEditingProfileName(null)
      setSiteConfig(payload.siteConfig ?? nextSelectedProfile?.config ?? payload.profiles[0]?.config ?? createDefaultSiteConfig())
      if (payload.runDraft) {
        setRunDraft(payload.runDraft)
      }
      setLocalError(null)
      setBackendStatus('Sites imported')
    } catch (importError) {
      setLocalError(`Sites import failed: ${formatUnknownError(importError)}`)
    } finally {
      event.target.value = ''
    }
  }, [])

  const handleAddConfiguration = useCallback(() => {
    setSelectedProfileName(null)
    setProfileName('')
    setEditingProfileName(null)
    setLocalError(null)
    setBackendStatus(null)
    setConfigDialogOpen(true)
  }, [])

  const handleOpenConfiguration = useCallback(() => {
    setProfileName(selectedProfileName ?? profileName)
    setEditingProfileName(selectedProfileName)
    setConfigDialogOpen(true)
  }, [profileName, selectedProfileName])

  const handleConfigDialogOpenChange = useCallback((open: boolean) => {
    setConfigDialogOpen(open)
    if (!open) {
      setEditingProfileName(null)
    }
  }, [])

  const waitForBackendJob = useCallback(async (
    jobRef: ActiveBackendJob,
    initialJob?: BackendJobStatusResponse,
  ) => {
    if (backendJobPollingRef.current === jobRef.id) {
      return
    }

    backendJobPollingRef.current = jobRef.id
    setRunning(true)
    setLocalError(null)

    try {
      let job = initialJob ?? await loadBackendJobStatus(jobRef.backendUrl, jobRef.id)
      setRunProgress(job.progress)

      while (!isBackendJobTerminal(job)) {
        await delay(1000)
        job = await loadBackendJobStatus(jobRef.backendUrl, jobRef.id)
        setRunProgress(job.progress)
      }

      if (job.status === 'completed') {
        if (job.summary) {
          onReport(job.summary)
        }
        setBackendStatus(`Backend job ${job.id} complete`)
        try {
          setHistoryItems(await listBackendRunHistory(jobRef.backendUrl))
          setHistoryError(null)
        } catch (historyErrorValue) {
          setHistoryError(historyErrorValue instanceof Error ? historyErrorValue.message : String(historyErrorValue))
        }
      } else {
        setLocalError(job.error ?? `Backend job ${job.id} failed`)
      }

      saveActiveBackendJob(null)
      setActiveBackendJob(null)
    } catch (jobError) {
      setLocalError(jobError instanceof Error ? jobError.message : String(jobError))
    } finally {
      if (backendJobPollingRef.current === jobRef.id) {
        backendJobPollingRef.current = null
      }
      setRunning(false)
    }
  }, [onReport])

  useEffect(() => {
    if (!activeBackendJob) {
      return
    }
    void waitForBackendJob(activeBackendJob)
  }, [activeBackendJob, waitForBackendJob])

  const handleRun = useCallback(async () => {
    setRunning(true)
    setLocalError(null)
    setRunProgress(EMPTY_RUN_PROGRESS)
    try {
      if (activeTargets.length === 0) {
        throw new Error('Enable at least one matrix target before running tests')
      }
      if (siteConfig.r9sBillingAuditEnabled && !siteConfig.r9sManagerKey.trim()) {
        throw new Error('R9S Manager Key is required when billing audit is enabled')
      }

      const headers = parseCustomHeaders(siteConfig.customHeaders)
      const timeoutMs = parsePositiveNumber(runDraft.settings.timeoutMs, 45_000)
      const concurrency = parsePositiveNumber(runDraft.settings.concurrency, 1)
      const runSnapshot = buildRunSnapshot(selectedProfileName, siteConfig, runDraft)
      const standardExecution = effectiveStandardExecution(siteConfig)
      const runUsesBackend = activeTargets.some((target) => (
        target.kind === 'agent' || standardExecution === 'backend'
      ))

      if (standardExecution === 'backend') {
        const initialJob = await createBackendJob(siteConfig.backendUrl, buildBackendJobRequest(
          selectedProfileName,
          siteConfig,
          activeTargets,
          headers,
          timeoutMs,
          concurrency,
          runSnapshot,
        ))
        const jobRef = { id: initialJob.id, backendUrl: siteConfig.backendUrl }
        saveActiveBackendJob(jobRef)
        setActiveBackendJob(jobRef)
        await waitForBackendJob(jobRef, initialJob)
        return
      }

      const summaries: RunSummary[] = []
      const progressTargets = activeTargets.map(createTargetProgress)
      const progressByTargetId = new Map(progressTargets.map((target) => [target.id, target]))
      const publishProgress = (): void => {
        setRunProgress(summarizeProgress(progressTargets))
      }
      const completeTarget = (target: RunTarget): void => {
        const progress = progressByTargetId.get(target.id)
        if (!progress) {
          return
        }
        progress.status = 'complete'
        progress.total = Math.max(progress.total, 1)
        progress.completed = progress.total
        publishProgress()
      }
      const failTarget = (target: RunTarget, targetError: unknown): void => {
        const progress = progressByTargetId.get(target.id)
        if (!progress) {
          return
        }
        progress.status = 'complete'
        progress.total = Math.max(progress.total, 1)
        progress.completed = progress.total
        progress.failed += 1
        progress.currentCase = targetError instanceof Error ? targetError.message : String(targetError)
        publishProgress()
      }
      const applyProgressEvent = (target: RunTarget, event: RunProgressEvent): void => {
        const progress = progressByTargetId.get(target.id)
        if (!progress) {
          return
        }
        progress.status = event.phase === 'provider-complete' ? 'complete' : 'running'
        progress.total = Math.max(event.total, 1)
        progress.completed = event.phase === 'provider-complete'
          ? progress.total
          : Math.min(event.completed, progress.total)
        if (event.phase === 'case-start') {
          progress.currentCase = event.caseId ?? event.description
        }
        if (event.phase === 'case-complete') {
          progress.currentCase = event.caseId ?? event.description
          if (event.status === 'passed') {
            progress.passed += 1
          } else if (event.status === 'failed') {
            progress.failed += 1
          } else if (event.status === 'skipped') {
            progress.skipped += 1
          }
        }
        if (event.phase === 'provider-complete') {
          progress.currentCase = `${event.provider} complete`
        }
        publishProgress()
      }
      const progressHandlerFor = (target: RunTarget): RunProgressHandler => (
        (event) => { applyProgressEvent(target, event) }
      )
      publishProgress()

      for (const target of activeTargets) {
        const model = getRunTargetModel(target)
        const modelLabel = getRunTargetModelLabel(target)
        try {
          if (target.kind === 'standard') {
            const config: PlatformRunConfig = {
              kind: 'standard',
              apiType: target.apiType,
              apiKey: emptyToUndefined(siteConfig.apiKey),
              apiBaseUrl: emptyToUndefined(siteConfig.apiBaseUrl),
              model,
              timeoutMs,
              targetCases: emptyToUndefined(target.targetCases),
              customHeaders: headers,
              apiVersion: emptyToUndefined(siteConfig.apiVersion),
              failFast: false,
              concurrency,
              persistResult: false,
              runSnapshot,
            }

            const report = await runBrowserStandardCases({
              apiType: target.apiType,
              apiKey: config.apiKey,
              apiBaseUrl: config.apiBaseUrl,
              model,
              timeoutMs,
              targetCases: config.targetCases,
              customHeaders: headers,
              apiVersion: config.apiVersion,
              failFast: false,
              onProgress: progressHandlerFor(target),
            })
            summaries.push(report)
            completeTarget(target)
          } else {
            summaries.push(await runBackendCases(siteConfig.backendUrl, {
              kind: 'agent',
              agentProvider: target.agentProvider,
              apiKey: emptyToUndefined(siteConfig.apiKey),
              apiBaseUrl: emptyToUndefined(siteConfig.apiBaseUrl),
              model: emptyToUndefined(model),
              timeoutMs,
              targetCases: emptyToUndefined(target.targetCases),
              customHeaders: headers,
              apiVersion: emptyToUndefined(siteConfig.apiVersion),
              failFast: false,
              concurrency,
              workingDirectory: emptyToUndefined(siteConfig.workingDirectory),
              skipGitRepoCheck: siteConfig.skipGitRepoCheck,
              testImagePath: emptyToUndefined(siteConfig.testImagePath),
              persistResult: false,
              runSnapshot,
            }, { onProgress: progressHandlerFor(target) }))
            completeTarget(target)
          }
        } catch (targetError) {
          failTarget(target, targetError)
          summaries.push(failedRunSummary(getRunTargetLabel(target), modelLabel, targetError))
        }
      }

      const merged = mergeRunSummaries(summaries)
      merged.runSnapshot = runSnapshot
      if (runUsesBackend) {
        try {
          await saveBackendRunReport(siteConfig.backendUrl, merged)
        } catch (historyErrorValue) {
          console.error('Failed to save backend run history', historyErrorValue)
        }
      }
      onReport(merged)
    } catch (runError) {
      setLocalError(runError instanceof Error ? runError.message : String(runError))
    } finally {
      setRunning(false)
    }
  }, [activeTargets, onReport, runDraft, selectedProfileName, siteConfig, waitForBackendJob])

  const handleCheckBackend = useCallback(async () => {
    setBackendStatus(null)
    setLocalError(null)
    try {
      const health = await checkBackendHealth(siteConfig.backendUrl)
      setBackendStatus(health.ok ? `${health.service ?? 'backend'} online` : 'backend unavailable')
    } catch (healthError) {
      setLocalError(healthError instanceof Error ? healthError.message : String(healthError))
    }
  }, [siteConfig.backendUrl])

  const handleRefreshHistory = useCallback(async () => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      setHistoryItems(await listBackendRunHistory(siteConfig.backendUrl))
    } catch (historyErrorValue) {
      setHistoryError(historyErrorValue instanceof Error ? historyErrorValue.message : String(historyErrorValue))
    } finally {
      setHistoryLoading(false)
    }
  }, [siteConfig.backendUrl])

  const handleLoadHistoryReport = useCallback(async (id: string) => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      onReport(await loadBackendRunHistoryReport(siteConfig.backendUrl, id))
    } catch (historyErrorValue) {
      setHistoryError(historyErrorValue instanceof Error ? historyErrorValue.message : String(historyErrorValue))
    } finally {
      setHistoryLoading(false)
    }
  }, [onReport, siteConfig.backendUrl])

  const handleExportHistoryReport = useCallback(async (entry: BackendRunHistoryEntry) => {
    setHistoryLoading(true)
    setHistoryError(null)
    try {
      const report = await loadBackendRunHistoryReport(siteConfig.backendUrl, entry.id)
      const baseName = entry.fileName.replace(/\.json$/i, '') || entry.id
      downloadJsonFile(`${sanitizeDownloadNamePart(baseName, 'history')}.json`, sanitizeRunSummaryForExport(report))
    } catch (historyErrorValue) {
      setHistoryError(formatUnknownError(historyErrorValue))
    } finally {
      setHistoryLoading(false)
    }
  }, [siteConfig.backendUrl])

  const handleDeleteHistoryReport = useCallback(async (entry: BackendRunHistoryEntry) => {
    if (!window.confirm(`Delete history record "${formatHistoryTitle(entry)}"?`)) {
      return
    }

    setHistoryLoading(true)
    setHistoryError(null)
    try {
      await deleteBackendRunHistory(siteConfig.backendUrl, entry.id)
      setHistoryItems((current) => current.filter((item) => item.id !== entry.id))
    } catch (historyErrorValue) {
      setHistoryError(formatUnknownError(historyErrorValue))
    } finally {
      setHistoryLoading(false)
    }
  }, [siteConfig.backendUrl])

  const handleClearHistory = useCallback(async () => {
    if (historyItems.length === 0 || !window.confirm(`Clear all ${historyItems.length} backend history records?`)) {
      return
    }

    setHistoryLoading(true)
    setHistoryError(null)
    try {
      await Promise.all(historyItems.map((entry) => deleteBackendRunHistory(siteConfig.backendUrl, entry.id)))
      setHistoryItems([])
    } catch (historyErrorValue) {
      setHistoryError(formatUnknownError(historyErrorValue))
      try {
        setHistoryItems(await listBackendRunHistory(siteConfig.backendUrl))
      } catch {
        // Keep the original clear error visible.
      }
    } finally {
      setHistoryLoading(false)
    }
  }, [historyItems, siteConfig.backendUrl])

  useEffect(() => {
    if (requiresBackend) {
      void handleRefreshHistory()
    }
  }, [handleRefreshHistory, requiresBackend])

  const handleFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      void onLoadFile(file)
      event.target.value = ''
    }
  }, [onLoadFile])

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-4 font-sans text-slate-900 md:p-5">
      <div className="mx-auto max-w-[1760px]">
        <header className="mb-5 grid grid-cols-1 items-center gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(360px,420px)]">
          <div className="flex items-center text-xl font-bold tracking-wide text-slate-900">
            <Layers className="mr-3 h-6 w-6 text-slate-700" />
            LLM Spec Platform
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <input
              ref={siteImportInputRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(event) => { void handleImportSitesFile(event) }}
            />
            <ConfigurationSelector
              profiles={profiles}
              selectedName={selectedProfile?.name ?? null}
              hasUnsavedChanges={hasUnsavedEnvironmentChanges}
              onSelect={handleLoadProfile}
              onAdd={handleAddConfiguration}
              onEdit={handleEditProfile}
              onDuplicate={handleDuplicateProfile}
              onDelete={handleDeleteProfile}
              onExport={handleExportSite}
            />
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => { siteImportInputRef.current?.click() }}
              aria-label="Import sites"
            >
              <Upload className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={handleExportSites}
              aria-label="Export sites"
            >
              <Download className="h-4 w-4" />
            </Button>
          </div>
        </header>

        <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(360px,420px)]">
          <div
            ref={runConsoleRef}
            className="flex flex-col overflow-hidden rounded-lg border border-slate-200/80 bg-white shadow-[0_2px_10px_-3px_rgba(6,81,237,0.05)]"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
              <h2 className="text-lg font-bold text-slate-800">Run Console</h2>
              <Button type="button" variant="outline" onClick={handleOpenConfiguration}>
                <Settings2 className="h-4 w-4" />
                Environment
              </Button>
            </div>

            <div className="flex-grow space-y-5 p-5">
              <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-4">
                <SummaryField
                  label="Environment"
                  value={selectedProfile?.name
                    ? `${selectedProfile.name}${hasUnsavedEnvironmentChanges ? ' *' : ''}`
                    : 'Unsaved environment'}
                  muted={!selectedProfile}
                />
                <SummaryField
                  label="Endpoint"
                  value={siteConfig.apiBaseUrl || 'Provider default'}
                  muted={!siteConfig.apiBaseUrl}
                />
                <SummaryField label="Execution" value={executionSummary} />
                <SummaryField
                  label="Headers"
                  value={customHeaderCount === null ? 'Invalid' : customHeaderCount > 0 ? `${customHeaderCount} custom` : 'None'}
                  muted={!customHeaderCount}
                />
              </dl>

              <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
                <div className="md:col-span-3">
                  <Field
                    label="Timeout Ms"
                    value={runDraft.settings.timeoutMs}
                    onChange={(value) => { updateRunSettings({ timeoutMs: value }) }}
                    type="number"
                  />
                </div>
                <div className="md:col-span-3">
                  <Field
                    label="Concurrency"
                    value={runDraft.settings.concurrency}
                    onChange={(value) => { updateRunSettings({ concurrency: value }) }}
                    type="number"
                  />
                </div>
                <div className="md:col-span-6">
                  <div className="space-y-1.5">
                    <label className="block text-sm font-semibold text-slate-700">Backend</label>
                    <button
                      type="button"
                      className="flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-50 sm:w-auto"
                      onClick={handleCheckBackend}
                      disabled={running}
                    >
                      <Server className="h-4 w-4" />
                      Check Backend
                    </button>
                  </div>
                </div>
              </div>

              <div className="space-y-2.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h3 className="text-base font-bold text-slate-800">Test Matrix</h3>
                  <div className="flex min-w-0 flex-col items-stretch gap-1.5">
                    <div className="flex flex-wrap justify-end gap-2">
                      <button
                        type="button"
                        className="flex w-full transform items-center justify-center rounded-lg bg-slate-900 px-6 py-2 text-sm font-semibold text-white shadow-md transition-all duration-150 hover:-translate-y-0.5 hover:bg-slate-800 hover:shadow-lg disabled:pointer-events-none disabled:opacity-50 sm:w-auto"
                        onClick={handleRun}
                        disabled={running || loading}
                      >
                        {running ? <RotateCcw className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" fill="currentColor" />}
                        {running ? 'Running...' : 'Run Tests'}
                      </button>
                      <Button type="button" variant="outline" size="sm" onClick={handleAddStandardTarget}>
                        <Plus className="h-4 w-4" />
                        API Target
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={handleAddAgentTarget}>
                        <Bot className="h-4 w-4" />
                        Agent Target
                      </Button>
                    </div>
                    <div className="flex w-full items-center justify-end gap-2 sm:w-[40rem]">
                      <span className={cn('w-56 truncate text-right text-xs font-semibold', progressTextColor)}>
                        {progressStatusText}
                      </span>
                      <span className="relative flex h-2.5 w-2.5 shrink-0">
                        {running && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />}
                        <span className={cn('relative inline-flex h-2.5 w-2.5 rounded-full', progressDotColor)} />
                      </span>
                      <div className="h-2 w-72 shrink-0 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={cn('h-full rounded-full transition-[width] duration-300 ease-out', progressBarColor)}
                          style={{ width: `${hasRunProgress ? runProgress.percent : 0}%` }}
                        />
                      </div>
                      <span className="w-10 shrink-0 text-right text-xs font-medium text-slate-500">
                        {hasRunProgress ? `${runProgress.percent}%` : 'Idle'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <div className="min-w-[860px]">
                    <div className="grid grid-cols-[2.25rem_7rem_13rem_13rem_minmax(18rem,1fr)_5.5rem] gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <div className="text-center">On</div>
                      <div>Kind</div>
                      <div>Surface</div>
                      <div>Model</div>
                      <div>Cases</div>
                      <div className="text-right">Actions</div>
                    </div>
                    {runDraft.targets.length === 0 ? (
                      <div className="px-4 py-8 text-center text-sm text-slate-500">
                        No targets configured.
                      </div>
                    ) : (
                      runDraft.targets.map((target) => (
                        <div
                          key={target.id}
                          className="grid grid-cols-[2.25rem_7rem_13rem_13rem_minmax(18rem,1fr)_5.5rem] items-start gap-3 border-b border-slate-100 px-3 py-2.5 last:border-b-0"
                        >
                          <div className="flex h-[46px] items-center justify-center">
                            <Checkbox
                              checked={target.enabled}
                              onCheckedChange={(checked) => {
                                updateTarget(target.id, (current) => ({ ...current, enabled: checked === true }))
                              }}
                            />
                          </div>
                          <select
                            className="block w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-sm text-slate-900 outline-none transition-shadow focus:ring-2 focus:ring-slate-900"
                            value={target.kind}
                            onChange={(event) => { handleTargetKindChange(target, event.target.value as RunTargetKind) }}
                          >
                            <option value="standard">API</option>
                            <option value="agent">Agent</option>
                          </select>
                          {target.kind === 'standard' ? (
                            <StandardApiSelect
                              value={target.apiType}
                              onChange={(apiType) => { handleStandardApiChange(target, apiType) }}
                            />
                          ) : (
                            <AgentProviderSelect
                              value={target.agentProvider}
                              onChange={(agentProvider) => { handleAgentProviderChange(target, agentProvider) }}
                            />
                          )}
                          <input
                            className="block w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-2 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-slate-900"
                            value={target.model}
                            onChange={(event) => {
                              const model = event.target.value
                              updateTarget(target.id, (current) => {
                                const nextTarget = { ...current, model } as RunTarget
                                const targetCases = pruneHiddenTargetCases(nextTarget)
                                return {
                                  ...nextTarget,
                                  targetCases: nextTarget.kind === 'agent'
                                    ? normalizeAgentTargetCases(nextTarget.agentProvider, targetCases)
                                    : targetCases,
                                }
                              })
                            }}
                            placeholder={getRunTargetModelLabel(target)}
                          />
                          <TargetCasesField
                            value={target.targetCases}
                            options={getRunTargetCaseOptions(target)}
                            modelQuickSelect={target.kind === 'standard'
                              ? {
                                  apiType: target.apiType,
                                  currentModel: getRunTargetModel(target),
                                  models: getCaseQuickSelectModels(target),
                                  allOptions: getAllRunTargetCaseOptions(target),
                                  onSelectModelCases: (model, targetCases) => {
                                    updateTarget(target.id, (current) => (
                                      current.kind === 'standard'
                                        ? { ...current, model, targetCases }
                                        : current
                                    ))
                                  },
                                }
                              : undefined}
                            onChange={(value) => {
                              updateTarget(target.id, (current) => ({ ...current, targetCases: value }))
                            }}
                          />
                          <div className="flex justify-end gap-1 pt-1">
                            <button
                              type="button"
                              className="rounded-md p-2 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600"
                              onClick={() => { handleRemoveTarget(target.id) }}
                              aria-label={`Remove ${getRunTargetLabel(target)}`}
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
            </div>

            {backendStatus && (
              <div className="mx-5 mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                {backendStatus}
              </div>
            )}
            {displayError && (
              <div className="mx-5 mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {displayError}
              </div>
            )}
          </div>

          <div
            className="flex min-h-0 flex-col gap-4 lg:h-[var(--run-console-height)]"
            style={{ '--run-console-height': runConsoleHeight ? `${runConsoleHeight}px` : 'auto' } as CSSProperties}
          >
            <div className="rounded-lg border border-slate-200/80 bg-white p-5 shadow-[0_2px_10px_-3px_rgba(6,81,237,0.05)]">
              <h3 className="mb-4 text-lg font-bold text-slate-800">Report</h3>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="space-y-2.5">
                <button
                  type="button"
                  className="group flex w-full items-center rounded-lg border border-slate-200 px-4 py-2.5 text-left shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => { fileInputRef.current?.click() }}
                  disabled={loading}
                >
                  <FileJson className="mr-3 h-5 w-5 text-slate-500 group-hover:text-slate-700" />
                  <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900">Load JSON</span>
                </button>

                <button
                  type="button"
                  className="group flex w-full items-center rounded-lg border border-slate-200 px-4 py-2.5 text-left shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50"
                  onClick={onLoadSample}
                  disabled={loading}
                >
                  <Database className="mr-3 h-5 w-5 text-slate-500 group-hover:text-slate-700" />
                  <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900">Demo Data</span>
                </button>

                <div className="pt-2">
                  <button
                    type="button"
                    className="flex items-center px-2 py-1 text-sm font-medium text-slate-500 transition-colors hover:text-slate-900"
                    onClick={() => {
                      setSiteConfig(createDefaultSiteConfig())
                      setRunDraft(createDefaultRunDraft())
                      setSelectedProfileName(null)
                      setProfileName('')
                      setLocalError(null)
                      setBackendStatus(null)
                      setRunProgress(EMPTY_RUN_PROGRESS)
                    }}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    Reset Inputs
                  </button>
                </div>
              </div>
            </div>

            <div className="flex min-h-0 flex-col rounded-lg border border-slate-200/80 bg-white p-5 shadow-[0_2px_10px_-3px_rgba(6,81,237,0.05)] lg:flex-1">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="flex min-w-0 items-center text-base font-bold text-slate-800">
                  <History className="mr-2 h-4 w-4 shrink-0 text-slate-500" />
                  <span className="truncate">Backend History</span>
                </h3>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    className="rounded-md p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-50"
                    onClick={() => { void handleRefreshHistory() }}
                    disabled={historyLoading}
                    aria-label="Refresh backend history"
                  >
                    <RefreshCw className={cn('h-4 w-4', historyLoading && 'animate-spin')} />
                  </button>
                  <button
                    type="button"
                    className="rounded-md p-2 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-500 disabled:pointer-events-none disabled:opacity-50"
                    onClick={() => { void handleClearHistory() }}
                    disabled={historyLoading || historyItems.length === 0}
                    aria-label="Clear backend history"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {historyError && (
                <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                  {historyError}
                </div>
              )}

              <div className="max-h-96 min-h-0 space-y-2 overflow-y-auto pr-1 lg:max-h-none lg:flex-1">
                {historyItems.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-slate-200 px-3 py-5 text-center text-sm text-slate-500">
                    {historyLoading ? 'Loading history...' : 'No saved backend runs'}
                  </div>
                ) : (
                  historyItems.map((entry) => (
                    <div
                      key={entry.id}
                      className={cn(
                        'group flex w-full items-start gap-2 rounded-lg border border-slate-200 px-3 py-2.5 text-left transition-colors hover:border-slate-300 hover:bg-slate-50',
                        (historyLoading || running) && 'opacity-50',
                      )}
                    >
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 items-start gap-3 text-left disabled:pointer-events-none"
                        onClick={() => { void handleLoadHistoryReport(entry.id) }}
                        disabled={historyLoading || running}
                      >
                        <FolderOpen className="mt-0.5 h-4 w-4 shrink-0 text-slate-400 group-hover:text-slate-700" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-slate-800">
                            {formatHistoryTitle(entry)}
                          </span>
                          <span className="mt-0.5 block truncate text-xs text-slate-500">
                            {formatDateTime(entry.finishedAt)}
                          </span>
                          <span className="mt-1 block truncate text-xs text-slate-500">
                            {formatHistorySubtitle(entry)}
                          </span>
                          <span className={cn(
                            'mt-1 block truncate text-xs font-semibold',
                            entry.totalFailed > 0 ? 'text-rose-600' : 'text-emerald-600',
                          )}
                          >
                            {formatHistoryOutcome(entry)}
                          </span>
                        </span>
                      </button>
                      <div className="flex shrink-0 gap-1">
                        <button
                          type="button"
                          className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-900 disabled:pointer-events-none"
                          onClick={() => { void handleExportHistoryReport(entry) }}
                          disabled={historyLoading || running}
                          aria-label={`Export ${formatHistoryTitle(entry)}`}
                        >
                          <Download className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          className="rounded-md p-1.5 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-500 disabled:pointer-events-none"
                          onClick={() => { void handleDeleteHistoryReport(entry) }}
                          disabled={historyLoading || running}
                          aria-label={`Delete ${formatHistoryTitle(entry)}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        <Dialog open={configDialogOpen} onOpenChange={handleConfigDialogOpenChange}>
          <DialogContent className="max-h-[90vh] max-w-[920px] gap-0 overflow-hidden p-0">
            <DialogHeader className="border-b border-slate-100 px-6 py-5 pr-12">
              <DialogTitle>{editingProfileName ? 'Edit Environment' : 'Environment'}</DialogTitle>
              <DialogDescription>
                Save connection details separately from the editable test matrix.
              </DialogDescription>
            </DialogHeader>

            <ScrollArea className="max-h-[calc(90vh-10rem)]">
              <div className="space-y-6 p-6">
                <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                  <Field
                    label="Environment Name"
                    value={profileName}
                    onChange={setProfileName}
                    placeholder="e.g. Gemini OpenAI Gateway"
                  />
                </div>

                <div className="flex w-fit rounded-lg border border-slate-200 bg-slate-100 p-1">
                  <ToggleButton
                    size="sm"
                    active={siteConfig.standardExecution === 'browser'}
                    value="browser"
                    onSelect={(value) => { updateSiteConfig({ standardExecution: value }) }}
                  >
                    <Wifi className="mr-1.5 h-3.5 w-3.5" />
                    Browser
                  </ToggleButton>
                  <ToggleButton
                    size="sm"
                    active={siteConfig.standardExecution === 'backend'}
                    value="backend"
                    onSelect={(value) => { updateSiteConfig({ standardExecution: value }) }}
                  >
                    <Server className="mr-1.5 h-3.5 w-3.5" />
                    Backend
                  </ToggleButton>
                </div>

                <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                  <Field
                    label="Base URL"
                    value={siteConfig.apiBaseUrl}
                    onChange={(value) => { updateSiteConfig({ apiBaseUrl: value }) }}
                    placeholder="Provider default"
                  />
                  <Field
                    label="API Key"
                    value={siteConfig.apiKey}
                    onChange={(value) => { updateSiteConfig({ apiKey: value }) }}
                    type="password"
                    autoComplete="off"
                  />
                  <Field
                    label="API Version"
                    value={siteConfig.apiVersion}
                    onChange={(value) => { updateSiteConfig({ apiVersion: value }) }}
                    placeholder="Gemini only"
                  />
                  <Field
                    label="Working Directory"
                    value={siteConfig.workingDirectory}
                    onChange={(value) => { updateSiteConfig({ workingDirectory: value }) }}
                    placeholder="Backend process cwd"
                  />
                  <Field
                    label="Test Image Path"
                    value={siteConfig.testImagePath}
                    onChange={(value) => { updateSiteConfig({ testImagePath: value }) }}
                    placeholder="Optional"
                  />
                  <div className="flex items-end">
                    <label className="flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-700">
                      <Checkbox
                        checked={siteConfig.skipGitRepoCheck}
                        onCheckedChange={(checked) => { updateSiteConfig({ skipGitRepoCheck: checked === true }) }}
                      />
                      Skip Git repo check
                    </label>
                  </div>
                </div>

                <CustomHeadersField
                  value={siteConfig.customHeaders}
                  onChange={(value) => { updateSiteConfig({ customHeaders: value }) }}
                />

                <div className="space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
                  <label className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                    <Checkbox
                      checked={siteConfig.r9sBillingAuditEnabled}
                      onCheckedChange={(checked) => {
                        updateSiteConfig(checked === true
                          ? { r9sBillingAuditEnabled: true, standardExecution: 'backend' }
                          : { r9sBillingAuditEnabled: false })
                      }}
                    />
                    <ReceiptText className="h-4 w-4 text-slate-500" />
                    R9S Billing Audit
                  </label>
                  {siteConfig.r9sBillingAuditEnabled && (
                    <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                      <Field
                        label="Manager Base URL"
                        value={siteConfig.r9sManagerBaseUrl}
                        onChange={(value) => { updateSiteConfig({ r9sManagerBaseUrl: value }) }}
                        placeholder={DEFAULT_R9S_MANAGER_BASE_URL}
                      />
                      <Field
                        label="Manager Key"
                        value={siteConfig.r9sManagerKey}
                        onChange={(value) => { updateSiteConfig({ r9sManagerKey: value }) }}
                        type="password"
                        autoComplete="off"
                      />
                      <Field
                        label="Token ID"
                        value={siteConfig.r9sTokenId}
                        onChange={(value) => { updateSiteConfig({ r9sTokenId: value }) }}
                        placeholder="tk_xxx"
                      />
                    </div>
                  )}
                </div>
              </div>
            </ScrollArea>

            <DialogFooter className="border-t border-slate-100 bg-slate-50/70 px-6 py-4">
              <Button type="button" variant="outline" onClick={() => { handleConfigDialogOpenChange(false) }}>
                Close
              </Button>
              <Button type="button" onClick={handleSaveProfile} disabled={!profileName.trim()}>
                <Save className="h-4 w-4" />
                Save Environment
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
