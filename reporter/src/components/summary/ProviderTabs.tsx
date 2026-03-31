import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Bot } from 'lucide-react'
import type { ProviderSummary } from '@/types'
import { formatProviderName, isAgentProvider } from '@/lib/format'
import { getProviderConfig } from '@/lib/constants'

interface ProviderTabsProps {
  providers: ProviderSummary[]
  activeProvider: string
  onProviderChange: (provider: string) => void
}

export function ProviderTabs({ providers, activeProvider, onProviderChange }: ProviderTabsProps) {
  return (
    <Tabs value={activeProvider} onValueChange={onProviderChange}>
      <TabsList className="flex-wrap h-auto gap-1 bg-slate-100 p-1 rounded-xl">
        <TabsTrigger
          value="__overview__"
          className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-lg px-4"
        >
          <span className="font-medium">Overview</span>
          <Badge variant="secondary" className="ml-2 text-xs">
            {providers.length}
          </Badge>
        </TabsTrigger>
        {providers.map((p) => {
          const config = getProviderConfig(p.provider)
          const isAgent = isAgentProvider(p.provider)
          return (
            <TabsTrigger
              key={p.provider}
              value={p.provider}
              className="data-[state=active]:bg-white data-[state=active]:shadow-sm rounded-lg px-4"
            >
              <config.icon className={`w-4 h-4 mr-1.5 ${config.color}`} />
              <span className="font-medium">{formatProviderName(p.provider)}</span>
              {isAgent && <Bot className="w-3 h-3 ml-1 text-amber-500" />}
              <Badge variant="secondary" className="ml-2 text-xs">
                {p.passed}/{p.passed + p.failed + p.skipped}
              </Badge>
            </TabsTrigger>
          )
        })}
      </TabsList>
    </Tabs>
  )
}
