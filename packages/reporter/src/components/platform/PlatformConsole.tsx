import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import {
  Bot,
  Check,
  ChevronsUpDown,
  Cloud,
  Database,
  Eye,
  EyeOff,
  FileJson,
  Layers,
  Pencil,
  Play,
  Plus,
  RotateCcw,
  Save,
  Search,
  Server,
  ServerCrash,
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
  OPENAI_CHAT_SERVED_MODEL_IDS,
  OPENAI_RESPONSES_SERVED_MODEL_IDS,
  runBrowserStandardCases,
} from '@/lib/browser-runner'
import { checkBackendHealth, runBackendCases } from '@/lib/backend-client'
import { cn } from '@/lib/utils'
import type {
  AgentProvider,
  PlatformRunConfig,
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
    defaultModel: 'claude-sonnet-4-6',
  },
  {
    value: 'codex',
    label: 'Codex',
    defaultModel: '',
  },
]

const DEFAULT_BACKEND_URL = import.meta.env.VITE_LLM_SPEC_BACKEND_URL ?? 'http://localhost:8788'

const STANDARD_TARGET_CASES: Record<StandardApiType, TargetCaseOption[]> = {
  'openai.chat': [
    ...caseOptions('Chat', [
      'basic',
      'sampling_and_max_completion',
      'max_tokens_legacy',
      'stop_sequences',
      'response_format_json_object',
      'response_format_json_schema',
      'tools_and_tool_choice',
      'stream_and_stream_options',
      'basic_stream',
      'sampling_and_max_completion_stream',
      'max_tokens_legacy_stream',
      'stop_sequences_stream',
      'response_format_json_object_stream',
      'response_format_json_schema_stream',
      'tools_and_tool_choice_stream',
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
    ...caseOptions(
      'OpenAI model catalog',
      OPENAI_CHAT_SERVED_MODEL_IDS.map((model) => modelCatalogCaseId('model_', model)),
    ),
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
  'openai.responses': caseOptions('Responses', [
    'responses_basic',
    'responses_sampling_and_limits',
    'responses_background_and_instructions',
    'responses_identity_and_cache',
    'responses_prompt_cache_round_trip',
    'responses_context_include_truncation',
    'responses_text_json_schema',
    'responses_tools',
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
    ...OPENAI_RESPONSES_SERVED_MODEL_IDS.map((model) =>
      modelCatalogCaseId('responses_model_', model),
    ),
  ]),
  'anthropic.messages': [
    ...caseOptions('Messages', [
      'basic',
      'different_model_haiku',
      'sampling_and_stop',
      'temperature_sampling',
      'system_metadata_service_tier',
      'output_config_json_schema',
      'tools_auto_choice',
      'tools_forced_choice',
      'thinking',
      'cache_control',
      'cache_control_round_trip',
      'inference_geo',
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
      'thinking_stream',
      'cache_control_stream',
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
    ]),
  ],
  'gemini.generateContent': [
    ...caseOptions('Generate Content', [
      'basic',
      'sampling_and_limits',
      'penalties',
      'logprobs',
      'system_labels_http_abort',
      'response_schema',
      'response_json_schema',
      'safety_settings',
      'tools_and_tool_config',
      'automatic_function_calling',
      'thinking_config',
      'labels',
      'cached_content',
      'audio_modality',
      'image_config',
      'routing_and_model_selection',
      'model_armor',
    ]),
    ...caseOptions('Streaming', [
      'stream',
      'basic_stream',
      'sampling_and_limits_stream',
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
  ],
}

const AGENT_TARGET_CASES: Record<AgentProvider, TargetCaseOption[]> = {
  'claude-agent': [
    ...caseOptions('Session', [
      'basic_prompt',
      'basic_session',
      'streaming_session',
      'multi_turn_conversation',
      'structured_output_json',
      'prompt_with_context',
    ]),
    ...caseOptions('Tools', [
      'tool_combination',
      'tool_execution_with_session',
      'multiple_tools_different_types',
    ]),
    ...caseOptions('Beta', [
      'beta_context_1m_basic',
      'beta_context_1m_with_session',
      'beta_thinking_adaptive',
      'beta_thinking_enabled',
      'beta_effort_low',
      'beta_effort_high',
      'beta_mcp_servers_config',
    ]),
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

function caseOptions(group: string, values: string[]): TargetCaseOption[] {
  return values.map((value) => ({
    value,
    label: formatCaseLabel(value),
    group,
  }))
}

function modelCatalogCaseId(prefix: 'model_' | 'responses_model_', model: string): string {
  return `${prefix}${model.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '')}`
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

function isGeminiOpenAICompatibilityModel(value: string): boolean {
  return value.trim().toLowerCase().startsWith('gemini-')
}

function getTargetCaseOptions(apiType: StandardApiType, model: string): TargetCaseOption[] {
  const options = STANDARD_TARGET_CASES[apiType]
  if (apiType !== 'openai.chat') {
    return options
  }

  const geminiCompatibility = isGeminiOpenAICompatibilityModel(model)
  return options.filter((option) => {
    if (option.group === 'Gemini compatibility') {
      return geminiCompatibility
    }
    if (option.group === 'OpenAI-specific') {
      return !geminiCompatibility
    }
    return true
  })
}

const SITE_STORAGE_KEY = 'llm-spec-site-profiles'
const RUN_DRAFT_STORAGE_KEY = 'llm-spec-run-draft'
const LAST_SITE_NAME_STORAGE_KEY = 'llm-spec-last-site-name'
const LAST_SITE_CONFIG_STORAGE_KEY = 'llm-spec-last-site'
const LEGACY_PROFILE_STORAGE_KEY = 'llm-spec-profiles'
const LEGACY_LAST_PROFILE_STORAGE_KEY = 'llm-spec-last-profile'

interface SavedProfile {
  name: string
  savedAt: string
  config: SiteProfileConfig
  legacyDraft?: RunDraft
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
  }
}

function createDefaultRunSettings(): RunSettings {
  return {
    timeoutMs: '45000',
    concurrency: '1',
    failFast: true,
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
    backendUrl: stringValue(value.backendUrl, defaults.backendUrl),
    standardExecution: normalizeStandardExecution(value.standardExecution),
    workingDirectory: stringValue(value.workingDirectory, defaults.workingDirectory),
    skipGitRepoCheck: booleanValue(value.skipGitRepoCheck, defaults.skipGitRepoCheck),
    testImagePath: stringValue(value.testImagePath, defaults.testImagePath),
  }
}

function normalizeRunSettings(value: unknown): RunSettings {
  const defaults = createDefaultRunSettings()
  if (!isRecord(value)) {
    return defaults
  }

  return {
    timeoutMs: stringValue(value.timeoutMs, defaults.timeoutMs),
    concurrency: stringValue(value.concurrency, defaults.concurrency),
    failFast: booleanValue(value.failFast, defaults.failFast),
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
    return {
      id,
      kind: 'agent',
      enabled,
      agentProvider,
      model: stringValue(value.model, option.defaultModel),
      targetCases,
    }
  }

  const apiType = isStandardApiType(value.apiType) ? value.apiType : 'openai.chat'
  const option = selectedStandardOption(apiType)
  return {
    id,
    kind: 'standard',
    enabled,
    apiType,
    model: stringValue(value.model, option.defaultModel),
    targetCases,
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
    JSON.stringify(profiles.map((profile) => ({
      name: profile.name,
      savedAt: profile.savedAt,
      config: profile.config,
    }))),
  )
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
    headers[key] = headerValue
  }
  return headers
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
  onSelect: (profile: SavedProfile) => void
  onAdd: () => void
  onEdit: (profile: SavedProfile) => void
  onDelete: (name: string) => void
}) {
  const { profiles, selectedName, onSelect, onAdd, onEdit, onDelete } = props
  const [open, setOpen] = useState(false)
  const selectedProfile = profiles.find((profile) => profile.name === selectedName)

  if (profiles.length === 0) {
    return (
      <Button type="button" onClick={onAdd} className="w-full sm:w-auto">
        <Plus className="w-4 h-4" />
        Add Site
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
          className="h-10 w-full justify-between gap-3 sm:w-72"
        >
          <span className="min-w-0 truncate text-left">
            {selectedProfile?.name ?? 'Select site'}
          </span>
          <ChevronsUpDown className="h-4 w-4 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(22rem,calc(100vw-2rem))] p-0">
        <div className="border-b border-slate-100 px-3 py-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Sites</span>
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
                      {profile.config.apiBaseUrl || profile.config.backendUrl || 'No endpoint'}
                    </span>
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
            Add Site
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
  agentToggles?: Array<{
    label: string
    enabled: boolean
    onToggle: () => void
  }>
}) {
  const { label, value, options, onChange, agentToggles } = props
  const enabledAgentLabels = agentToggles?.filter((a) => a.enabled) ?? []
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
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

  const updateValues = useCallback((nextValues: string[]) => {
    onChange(serializeTargetCaseValue(nextValues))
  }, [onChange])

  const toggleValue = useCallback((value: string) => {
    if (selectedSet.has(value)) {
      updateValues(selectedValues.filter((item) => item !== value))
      return
    }
    updateValues([...selectedValues, value])
  }, [selectedSet, selectedValues, updateValues])

  const selectVisible = useCallback(() => {
    updateValues([...selectedValues, ...filteredOptions.map((option) => option.value)])
  }, [filteredOptions, selectedValues, updateValues])

  const removeValue = useCallback((value: string) => {
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
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2">
            <span className="text-xs text-slate-500">
              {selectedValues.length === 0 ? 'No filter selected' : `${selectedValues.length} case filters`}
            </span>
            <div className="flex gap-2">
              <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={selectVisible}>
                Select visible
              </Button>
              <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => { updateValues([]) }}>
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
    return target.model.trim() || getAgentOption(target.agentProvider).defaultModel || 'Default'
  }
  return target.model.trim() || selectedStandardOption(target.apiType).defaultModel
}

function getRunTargetCaseOptions(target: RunTarget): TargetCaseOption[] {
  if (target.kind === 'agent') {
    return AGENT_TARGET_CASES[target.agentProvider]
  }
  return getTargetCaseOptions(target.apiType, target.model)
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

function buildRunSnapshot(
  siteName: string | null,
  site: SiteProfileConfig,
  draft: RunDraft,
): RunSnapshot {
  return {
    siteName: siteName ?? undefined,
    apiBaseUrl: emptyToUndefined(site.apiBaseUrl),
    backendUrl: emptyToUndefined(site.backendUrl),
    standardExecution: site.standardExecution,
    timeoutMs: parsePositiveNumber(draft.settings.timeoutMs, 45_000),
    concurrency: parsePositiveNumber(draft.settings.concurrency, 1),
    failFast: draft.settings.failFast,
    targets: draft.targets.map((target) => ({
      kind: target.kind,
      enabled: target.enabled,
      apiType: target.kind === 'standard' ? target.apiType : undefined,
      agentProvider: target.kind === 'agent' ? target.agentProvider : undefined,
      model: getRunTargetModel(target),
      targetCases: emptyToUndefined(target.targetCases),
      execution: target.kind === 'agent' ? 'backend' : site.standardExecution,
    })),
  }
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
  const [localError, setLocalError] = useState<string | null>(null)
  const [backendStatus, setBackendStatus] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const initialProfileLoadedRef = useRef(false)

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
    localStorage.setItem(LAST_SITE_CONFIG_STORAGE_KEY, JSON.stringify(siteConfig))
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
  const activeTargets = useMemo(
    () => runDraft.targets.filter((target) => target.enabled),
    [runDraft.targets],
  )
  const standardTargetCount = activeTargets.filter((target) => target.kind === 'standard').length
  const agentTargetCount = activeTargets.filter((target) => target.kind === 'agent').length
  const selectedCaseCount = runDraft.targets.reduce(
    (sum, target) => sum + parseTargetCaseValue(target.targetCases).length,
    0,
  )
  const requiresBackend = siteConfig.standardExecution === 'backend' || agentTargetCount > 0
  const executionSummary = (() => {
    if (siteConfig.standardExecution === 'backend') {
      return 'Backend service'
    }
    if (agentTargetCount > 0) {
      return 'Browser + backend agents'
    }
    return 'Browser fetch'
  })()
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
    setSiteConfig(profile.config)
    if (profile.legacyDraft) {
      setRunDraft(profile.legacyDraft)
    }
    setSelectedProfileName(profile.name)
    setProfileName(profile.name)
    setLocalError(null)
    setBackendStatus(null)
  }, [])

  const handleEditProfile = useCallback((profile: SavedProfile) => {
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
  }, [])

  const handleDeleteProfile = useCallback((name: string) => {
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

  const handleRun = useCallback(async () => {
    setRunning(true)
    setLocalError(null)
    setRunProgress(EMPTY_RUN_PROGRESS)
    try {
      if (activeTargets.length === 0) {
        throw new Error('Enable at least one matrix target before running tests')
      }

      const headers = parseCustomHeaders(siteConfig.customHeaders)
      const timeoutMs = parsePositiveNumber(runDraft.settings.timeoutMs, 45_000)
      const concurrency = parsePositiveNumber(runDraft.settings.concurrency, 1)
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
              failFast: runDraft.settings.failFast,
              concurrency,
            }

            const report = siteConfig.standardExecution === 'backend'
              ? await runBackendCases(siteConfig.backendUrl, config, { onProgress: progressHandlerFor(target) })
              : await runBrowserStandardCases({
                apiType: target.apiType,
                apiKey: config.apiKey,
                apiBaseUrl: config.apiBaseUrl,
                model,
                timeoutMs,
                targetCases: config.targetCases,
                customHeaders: headers,
                apiVersion: config.apiVersion,
                failFast: config.failFast,
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
              model,
              timeoutMs,
              targetCases: emptyToUndefined(target.targetCases),
              customHeaders: headers,
              apiVersion: emptyToUndefined(siteConfig.apiVersion),
              failFast: runDraft.settings.failFast,
              concurrency,
              workingDirectory: emptyToUndefined(siteConfig.workingDirectory),
              skipGitRepoCheck: siteConfig.skipGitRepoCheck,
              testImagePath: emptyToUndefined(siteConfig.testImagePath),
            }, { onProgress: progressHandlerFor(target) }))
            completeTarget(target)
          }
        } catch (targetError) {
          failTarget(target, targetError)
          summaries.push(failedRunSummary(getRunTargetLabel(target), model, targetError))
        }
      }

      const merged = mergeRunSummaries(summaries)
      merged.runSnapshot = buildRunSnapshot(selectedProfileName, siteConfig, runDraft)
      onReport(merged)
    } catch (runError) {
      setLocalError(runError instanceof Error ? runError.message : String(runError))
    } finally {
      setRunning(false)
    }
  }, [activeTargets, onReport, runDraft, selectedProfileName, siteConfig])

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

  const handleFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      void onLoadFile(file)
      event.target.value = ''
    }
  }, [onLoadFile])

  return (
    <div className="min-h-screen bg-[#F8F9FB] p-6 font-sans text-slate-900 md:p-10">
      <div className="mx-auto max-w-[1280px]">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center text-xl font-bold tracking-wide text-slate-900">
            <Layers className="mr-3 h-6 w-6 text-slate-700" />
            LLM Spec Platform
          </div>
          <ConfigurationSelector
            profiles={profiles}
            selectedName={selectedProfile?.name ?? null}
            onSelect={handleLoadProfile}
            onAdd={handleAddConfiguration}
            onEdit={handleEditProfile}
            onDelete={handleDeleteProfile}
          />
        </header>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          <div className="flex flex-col overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-[0_2px_10px_-3px_rgba(6,81,237,0.05)] lg:col-span-8">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 px-6 py-5">
              <h2 className="text-lg font-bold text-slate-800">Run Console</h2>
              <Button type="button" variant="outline" onClick={handleOpenConfiguration}>
                <Settings2 className="h-4 w-4" />
                Site
              </Button>
            </div>

            <div className="flex-grow space-y-6 p-6">
              <dl className="grid grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">
                <SummaryField
                  label="Site"
                  value={selectedProfile?.name ?? 'Unsaved site'}
                  muted={!selectedProfile}
                />
                <SummaryField
                  label="Targets"
                  value={`${activeTargets.length} enabled / ${runDraft.targets.length} total`}
                  muted={activeTargets.length === 0}
                />
                <SummaryField
                  label="Model Rows"
                  value={`${standardTargetCount} API, ${agentTargetCount} agent`}
                />
                <SummaryField label="Execution" value={executionSummary} />
                <SummaryField
                  label="Target Cases"
                  value={selectedCaseCount > 0 ? `${selectedCaseCount} filters` : 'All cases'}
                  muted={selectedCaseCount === 0}
                />
                <SummaryField
                  label="Endpoint"
                  value={siteConfig.apiBaseUrl || 'Provider default'}
                  muted={!siteConfig.apiBaseUrl}
                />
              </dl>

              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3 className="text-base font-bold text-slate-800">Test Matrix</h3>
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" variant="outline" size="sm" onClick={handleAddStandardTarget}>
                      <Plus className="h-4 w-4" />
                      API Target
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={handleAddAgentTarget}>
                      <Bot className="h-4 w-4" />
                      Agent Target
                    </Button>
                  </div>
                </div>

                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <div className="min-w-[860px]">
                    <div className="grid grid-cols-[3rem_7rem_13rem_13rem_minmax(18rem,1fr)_5.5rem] gap-3 border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      <div>On</div>
                      <div>Kind</div>
                      <div>Surface</div>
                      <div>Model</div>
                      <div>Cases</div>
                      <div className="text-right">Actions</div>
                    </div>
                    {runDraft.targets.length === 0 ? (
                      <div className="px-4 py-10 text-center text-sm text-slate-500">
                        No targets configured.
                      </div>
                    ) : (
                      runDraft.targets.map((target) => (
                        <div
                          key={target.id}
                          className="grid grid-cols-[3rem_7rem_13rem_13rem_minmax(18rem,1fr)_5.5rem] items-start gap-3 border-b border-slate-100 px-3 py-3 last:border-b-0"
                        >
                          <div className="pt-2">
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
                              updateTarget(target.id, (current) => ({ ...current, model: event.target.value }))
                            }}
                            placeholder={getRunTargetModel(target)}
                          />
                          <TargetCasesField
                            value={target.targetCases}
                            options={getRunTargetCaseOptions(target)}
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

              <div className="grid grid-cols-1 gap-5 border-t border-slate-100 pt-5 md:grid-cols-12">
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
                <div className="flex items-end md:col-span-3">
                  <label className="flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-700">
                    <Checkbox
                      checked={runDraft.settings.failFast}
                      onCheckedChange={(checked) => { updateRunSettings({ failFast: checked === true }) }}
                    />
                    Fail fast
                  </label>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 bg-slate-50/50 px-6 py-4">
              <div className="text-sm text-slate-500">
                {requiresBackend ? `Backend: ${siteConfig.backendUrl}` : 'Standard API targets will run from the browser'}
              </div>

              <div className="flex w-full items-center gap-3 sm:w-auto">
                <button
                  type="button"
                  className="flex flex-1 items-center justify-center rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900 disabled:pointer-events-none disabled:opacity-50 sm:flex-none"
                  onClick={handleCheckBackend}
                  disabled={running || !requiresBackend}
                >
                  <ServerCrash className="mr-2 h-4 w-4 text-slate-400" />
                  Check Backend
                </button>
                <button
                  type="button"
                  className="flex flex-1 transform items-center justify-center rounded-lg bg-slate-900 px-6 py-2 text-sm font-semibold text-white shadow-md transition-all duration-150 hover:-translate-y-0.5 hover:bg-slate-800 hover:shadow-lg disabled:pointer-events-none disabled:opacity-50 sm:flex-none"
                  onClick={handleRun}
                  disabled={running || loading}
                >
                  {running ? <RotateCcw className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" fill="currentColor" />}
                  {running ? 'Running...' : 'Run Tests'}
                </button>
              </div>
            </div>

            {backendStatus && (
              <div className="mx-6 mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                {backendStatus}
              </div>
            )}
            {displayError && (
              <div className="mx-6 mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {displayError}
              </div>
            )}
          </div>

          <div className="space-y-6 lg:col-span-4">
            <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-[0_2px_10px_-3px_rgba(6,81,237,0.05)]">
              <h3 className="mb-5 text-lg font-bold text-slate-800">Report</h3>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={handleFileChange}
              />
              <div className="space-y-3">
                <button
                  type="button"
                  className="group flex w-full items-center rounded-xl border border-slate-200 px-4 py-3 text-left shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50"
                  onClick={() => { fileInputRef.current?.click() }}
                  disabled={loading}
                >
                  <FileJson className="mr-3 h-5 w-5 text-slate-500 group-hover:text-slate-700" />
                  <span className="text-sm font-semibold text-slate-700 group-hover:text-slate-900">Load JSON</span>
                </button>

                <button
                  type="button"
                  className="group flex w-full items-center rounded-xl border border-slate-200 px-4 py-3 text-left shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50 disabled:opacity-50"
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

            <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-[0_2px_10px_-3px_rgba(6,81,237,0.05)]">
              <h3 className="mb-4 text-base font-bold text-slate-800">Progress</h3>

              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <span className="relative flex h-3 w-3">
                    {running && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />}
                    <span className={cn('relative inline-flex h-3 w-3 rounded-full', progressDotColor)} />
                  </span>
                  <span className={cn('text-sm font-semibold', progressTextColor)}>
                    {progressStatusText}
                  </span>
                </div>

                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={cn('h-full rounded-full transition-[width] duration-300 ease-out', progressBarColor)}
                    style={{ width: `${hasRunProgress ? runProgress.percent : 0}%` }}
                  />
                </div>

                <div className="space-y-1.5 pt-1 text-xs text-slate-500">
                  <div className="flex items-center gap-2">
                    <Check className="h-3 w-3 text-slate-400" />
                    {hasRunProgress
                      ? `${runProgress.detailText} (${runProgress.percent}%)`
                      : 'Waiting for a run'}
                  </div>
                  {hasRunProgress && (
                    <div className="flex items-center gap-2">
                      <Check className="h-3 w-3 text-emerald-500" />
                      {runProgress.passed} passed, {runProgress.failed} failed, {runProgress.skipped} skipped
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Cloud className="h-3 w-3 text-slate-400" />
                    {activeTargets.length} enabled target{activeTargets.length === 1 ? '' : 's'}
                  </div>
                  <div className="flex items-center gap-2">
                    <Server className="h-3 w-3 text-slate-400" />
                    {selectedProfile?.name ?? 'Unsaved site'}
                  </div>
                  <div className="flex items-center gap-2">
                    {requiresBackend ? <Server className="h-3 w-3 text-slate-400" /> : <Wifi className="h-3 w-3 text-slate-400" />}
                    {executionSummary}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <Dialog open={configDialogOpen} onOpenChange={handleConfigDialogOpenChange}>
          <DialogContent className="max-h-[90vh] max-w-[920px] gap-0 overflow-hidden p-0">
            <DialogHeader className="border-b border-slate-100 px-6 py-5 pr-12">
              <DialogTitle>{editingProfileName ? 'Edit Site Profile' : 'Site Profile'}</DialogTitle>
              <DialogDescription>
                Save connection details separately from the editable test matrix.
              </DialogDescription>
            </DialogHeader>

            <ScrollArea className="max-h-[calc(90vh-10rem)]">
              <div className="space-y-6 p-6">
                <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                  <Field
                    label="Site Name"
                    value={profileName}
                    onChange={setProfileName}
                    placeholder="e.g. Gemini OpenAI Gateway"
                  />
                  <Field
                    label="Backend URL"
                    value={siteConfig.backendUrl}
                    onChange={(value) => { updateSiteConfig({ backendUrl: value }) }}
                    placeholder="http://localhost:8788"
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

                <TextAreaField
                  label="Custom Headers"
                  value={siteConfig.customHeaders}
                  onChange={(value) => { updateSiteConfig({ customHeaders: value }) }}
                  placeholder='{"X-Debug-Channel-ID":"13"}'
                />
              </div>
            </ScrollArea>

            <DialogFooter className="border-t border-slate-100 bg-slate-50/70 px-6 py-4">
              <Button type="button" variant="outline" onClick={() => { handleConfigDialogOpenChange(false) }}>
                Close
              </Button>
              <Button type="button" onClick={handleSaveProfile} disabled={!profileName.trim()}>
                <Save className="h-4 w-4" />
                Save Site
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
