import {
  Bot,
  Brain,
  Code,
  Globe,
  MessageSquare,
  type LucideIcon,
} from 'lucide-react'

export interface ProviderConfig {
  label: string
  icon: LucideIcon
  color: string
  bgColor: string
  borderColor: string
}

const PROVIDER_CONFIGS: Record<string, ProviderConfig> = {
  openai: {
    label: 'OpenAI',
    icon: MessageSquare,
    color: 'text-green-600',
    bgColor: 'bg-green-100',
    borderColor: 'border-green-200',
  },
  anthropic: {
    label: 'Anthropic',
    icon: Brain,
    color: 'text-orange-600',
    bgColor: 'bg-orange-100',
    borderColor: 'border-orange-200',
  },
  gemini: {
    label: 'Gemini',
    icon: Globe,
    color: 'text-blue-600',
    bgColor: 'bg-blue-100',
    borderColor: 'border-blue-200',
  },
  'claude-agent': {
    label: 'Claude Agent',
    icon: Bot,
    color: 'text-purple-600',
    bgColor: 'bg-purple-100',
    borderColor: 'border-purple-200',
  },
  codex: {
    label: 'Codex',
    icon: Code,
    color: 'text-teal-600',
    bgColor: 'bg-teal-100',
    borderColor: 'border-teal-200',
  },
}

const DEFAULT_CONFIG: ProviderConfig = {
  label: 'Unknown',
  icon: MessageSquare,
  color: 'text-slate-600',
  bgColor: 'bg-slate-100',
  borderColor: 'border-slate-200',
}

export function getProviderConfig(provider: string): ProviderConfig {
  for (const [key, config] of Object.entries(PROVIDER_CONFIGS)) {
    if (provider.includes(key)) return config
  }
  return DEFAULT_CONFIG
}
