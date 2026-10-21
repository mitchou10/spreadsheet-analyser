import { useState } from 'react'
import { ChartColumn } from 'lucide-react'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { useUsage } from '@/hooks/useUsage'
import { PeriodSelector, UsageCharts } from './UsageCharts'

/** My own token consumption. */
export function UsageView() {
  const [days, setDays] = useState(30)
  const { usage, error, isLoading } = useUsage(days)

  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <ChartColumn className="size-4 text-muted-foreground" aria-hidden />
          <span className="text-sm font-medium">Ma consommation</span>
        </div>
        <PeriodSelector days={days} onChange={setDays} />
      </div>
      <div className="flex-1 overflow-auto p-6">
        {error && (
          <p role="alert" className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
        {isLoading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {usage && usage.totals.calls === 0 && (
          <p className="py-12 text-center text-muted-foreground">Aucune consommation sur les {days} derniers jours.</p>
        )}
        {usage && usage.totals.calls > 0 && <UsageCharts usage={usage} />}
      </div>
    </div>
  )
}
