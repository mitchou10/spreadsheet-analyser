import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Usage, UsageSums } from '@/types/usage'

const PERIODS = [7, 30, 90] as const

// The agent graph nodes that call the model (agent-worker/app/agent/graph.py).
const NODE_LABELS: Record<string, string> = { plan: 'Plan', agent: 'Réponse / choix d’outil' }

const count = (n: number) => n.toLocaleString('fr-FR')
const compact = (n: number) => new Intl.NumberFormat('fr-FR', { notation: 'compact', maximumFractionDigits: 1 }).format(n)
const dayLabel = (day: string) => new Date(`${day}T00:00:00`).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })

export function PeriodSelector({ days, onChange }: { days: number; onChange: (days: number) => void }) {
  return (
    <div className="flex gap-1" role="group" aria-label="Période">
      {PERIODS.map((period) => (
        <Button key={period} size="sm" variant={days === period ? 'default' : 'outline'} onClick={() => onChange(period)}>
          {period} jours
        </Button>
      ))}
    </div>
  )
}

function Legend() {
  return (
    <ul className="flex gap-4 text-xs text-muted-foreground" aria-label="Légende">
      <li className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-usage-input" aria-hidden />
        Entrée (prompt)
      </li>
      <li className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-sm bg-usage-output" aria-hidden />
        Sortie (réponse)
      </li>
    </ul>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-1">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-2xl font-semibold tabular-nums">{count(value)}</span>
      </CardContent>
    </Card>
  )
}

/** Every day of the period, the ones without a call at zero, so the bars keep a regular time axis. */
function filledDays(usage: Usage): (UsageSums & { day: string })[] {
  const byDay = new Map(usage.byDay.map((d) => [d.day, d]))
  const days: (UsageSums & { day: string })[] = []
  const today = new Date()
  for (let offset = usage.days - 1; offset >= 0; offset--) {
    const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset)
    const day = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    days.push(byDay.get(day) ?? { day, inputTokens: 0, outputTokens: 0, totalTokens: 0, calls: 0 })
  }
  return days
}

function DailyChart({ usage }: { usage: Usage }) {
  const [hovered, setHovered] = useState<(UsageSums & { day: string }) | null>(null)
  const days = filledDays(usage)
  const max = Math.max(1, ...days.map((d) => d.totalTokens))

  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-5 items-center justify-between text-xs text-muted-foreground" aria-live="polite">
        <span>{hovered ? dayLabel(hovered.day) : 'Par jour'}</span>
        <span className="tabular-nums">
          {hovered ? `${count(hovered.inputTokens)} entrée · ${count(hovered.outputTokens)} sortie · ${hovered.calls} appel${hovered.calls > 1 ? 's' : ''}` : `max ${compact(max)}`}
        </span>
      </div>
      <div className="flex h-44 items-end gap-0.5 border-b" role="img" aria-label="Tokens consommés par jour">
        {days.map((d) => (
          <div
            key={d.day}
            className="flex h-full min-w-0 flex-1 cursor-default flex-col justify-end gap-0.5 hover:bg-muted/60"
            title={`${dayLabel(d.day)} : ${count(d.totalTokens)} tokens`}
            onMouseEnter={() => setHovered(d)}
            onMouseLeave={() => setHovered(null)}
          >
            <div className="rounded-t-sm bg-usage-output" style={{ height: `${(d.outputTokens / max) * 100}%` }} />
            <div className="bg-usage-input" style={{ height: `${(d.inputTokens / max) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{dayLabel(days[0].day)}</span>
        <span>{dayLabel(days[days.length - 1].day)}</span>
      </div>
    </div>
  )
}

interface Row extends UsageSums {
  key: string
  label: string
}

/** One horizontal bar per row (input + output stacked), biggest first: where the tokens go. */
function BarList({ rows, onSelect, selected }: { rows: Row[]; onSelect?: (key: string) => void; selected?: string | null }) {
  const max = Math.max(1, ...rows.map((r) => r.totalTokens))
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">Aucune consommation sur la période.</p>

  return (
    <>
      <ul className="flex flex-col gap-2.5">
        {rows.map((row) => {
          const bar = (
            <>
              <span className="flex justify-between gap-2 text-sm">
                <span className="truncate">{row.label}</span>
                <span className="shrink-0 tabular-nums text-muted-foreground">{count(row.totalTokens)}</span>
              </span>
              <span
                className="mt-1 flex h-2.5 gap-0.5"
                style={{ width: `${(row.totalTokens / max) * 100}%` }}
                title={`${row.label} : ${count(row.inputTokens)} entrée · ${count(row.outputTokens)} sortie · ${row.calls} appel${row.calls > 1 ? 's' : ''}`}
              >
                <span className="rounded-l-sm bg-usage-input" style={{ flex: row.inputTokens }} />
                <span className="rounded-r-sm bg-usage-output" style={{ flex: row.outputTokens }} />
              </span>
            </>
          )
          return (
            <li key={row.key}>
              {onSelect ? (
                <button
                  type="button"
                  aria-pressed={selected === row.key}
                  className={`block w-full rounded-md p-1.5 text-left hover:bg-muted ${selected === row.key ? 'bg-muted' : ''}`}
                  onClick={() => onSelect(row.key)}
                >
                  {bar}
                </button>
              ) : (
                <div className="p-1.5">{bar}</div>
              )}
            </li>
          )
        })}
      </ul>
      <details className="mt-3 text-xs text-muted-foreground">
        <summary className="w-fit cursor-pointer select-none">Voir en tableau</summary>
        <table className="mt-2 w-full border-collapse">
          <thead>
            <tr className="text-left">
              <th className="py-1 font-medium">Nom</th>
              <th className="py-1 text-right font-medium">Entrée</th>
              <th className="py-1 text-right font-medium">Sortie</th>
              <th className="py-1 text-right font-medium">Appels</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-t">
                <td className="py-1">{row.label}</td>
                <td className="py-1 text-right tabular-nums">{count(row.inputTokens)}</td>
                <td className="py-1 text-right tabular-nums">{count(row.outputTokens)}</td>
                <td className="py-1 text-right tabular-nums">{count(row.calls)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/** Totals, per-day evolution and the split per node and model; with `onSelectUser`, the split per person too. */
export function UsageCharts({
  usage,
  onSelectUser,
  selectedUser,
}: {
  usage: Usage
  onSelectUser?: (userId: string) => void
  selectedUser?: string | null
}) {
  const nodes = usage.byNode.map((n) => ({ ...n, key: n.node, label: NODE_LABELS[n.node] ?? n.node }))
  const models = usage.byModel.map((m) => ({ ...m, key: m.model ?? '-', label: m.model ?? 'Modèle inconnu' }))
  const users = usage.byUser.map((u) => ({ ...u, key: u.userId, label: u.email ?? `utilisateur ${u.userId}` }))

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total" value={usage.totals.totalTokens} />
        <Stat label="Entrée (prompt)" value={usage.totals.inputTokens} />
        <Stat label="Sortie (réponse)" value={usage.totals.outputTokens} />
        <Stat label="Appels au modèle" value={usage.totals.calls} />
      </div>
      <Legend />
      <Panel title="Tokens par jour">
        <DailyChart usage={usage} />
      </Panel>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Par nœud du graphe">
          <BarList rows={nodes} />
        </Panel>
        <Panel title="Par modèle">
          <BarList rows={models} />
        </Panel>
      </div>
      {onSelectUser && (
        <Panel title="Par utilisateur">
          <BarList rows={users} onSelect={onSelectUser} selected={selectedUser} />
        </Panel>
      )}
    </div>
  )
}
