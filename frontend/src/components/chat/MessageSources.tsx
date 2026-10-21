import type { MessageTrace } from '@/types/conversation'
import { ChevronRight, Wrench } from 'lucide-react'
import { isBackendImage } from '@/lib/backendImage'
import { ChatImage } from './ChatImage'
import { Markdown } from './Markdown'
import { ScopeChip } from './ScopeChip'

// The agent's tools (agent-worker/app/agent/tools.py), named for people.
const TOOL_LABELS: Record<string, string> = {
  list_files: 'Liste des fichiers',
  search: 'Recherche de colonnes',
  search_values: 'Recherche de valeurs',
  describe_sheet: 'Détail d’une feuille',
  describe_column: 'Détail d’une colonne',
  query_data: 'Requête SQL',
  create_chart: 'Graphique',
  account_overview: 'Vue d’ensemble du compte',
  account_files: 'Fichiers du compte',
}

// The graph nodes that call the model (agent-worker/app/agent/graph.py).
const NODE_LABELS: Record<string, string> = { plan: 'Plan', agent: 'Réponse / choix d’outil' }

const nodeLabel = (node: string) => NODE_LABELS[node] ?? node
const tokens = (count: number) => count.toLocaleString('fr-FR')

const toolLabel = (tool: string) => TOOL_LABELS[tool] ?? tool

/** A fenced code block that its own content cannot close early (a longer fence than any run of backticks inside). */
function fenced(text: string, language: string): string {
  const longest = Math.max(0, ...(text.match(/`+/g) ?? []).map((run) => run.length))
  const fence = '`'.repeat(Math.max(3, longest + 1))
  return `${fence}${language}\n${text}\n${fence}`
}

/** What a tool gave back, as markdown: JSON (what most tools return) indented in a code block, text (errors,
 * messages for the model) as it is. */
function outputAsMarkdown(output: string): string {
  try {
    const parsed = JSON.parse(output)
    if (parsed !== null && typeof parsed === 'object') return fenced(JSON.stringify(parsed, null, 2), 'json')
  } catch {
    // not JSON: it is text
  }
  return output
}

interface QueryResult {
  columns: string[]
  rows: unknown[][]
  note?: string
}

/** The output of `query_data` when it ran (an error comes back as text, not as this shape). */
function asQueryResult(output: string): QueryResult | null {
  try {
    const parsed = JSON.parse(output)
    return Array.isArray(parsed?.columns) && Array.isArray(parsed?.rows) ? parsed : null
  } catch {
    return null
  }
}

const cellText = (value: unknown) => (value === null || value === undefined ? '∅' : typeof value === 'object' ? JSON.stringify(value) : String(value))

function QueryStep({ sql, output }: { sql: string; output: string }) {
  const result = asQueryResult(output)
  return (
    <div className="flex flex-col gap-2 border-t px-2.5 py-2">
      <div className="text-[11px] [&_pre]:my-0 [&_pre]:bg-muted/70">
        <Markdown>{fenced(sql, 'sql')}</Markdown>
      </div>
      {result ? (
        <>
          <div className="max-h-64 overflow-auto rounded-md border">
            <table className="w-full border-collapse text-[11px]">
              <thead className="sticky top-0 bg-muted">
                <tr>
                  {result.columns.map((column) => (
                    <th key={column} className="border-b px-2 py-1 text-left font-medium">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, index) => (
                  <tr key={index} className="odd:bg-background even:bg-muted/30">
                    {row.map((cell, position) => (
                      <td key={position} className="px-2 py-1 align-top">
                        {cellText(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-muted-foreground">
            {result.rows.length} ligne{result.rows.length > 1 ? 's' : ''}
            {result.note ? ` · ${result.note}` : ''}
          </p>
        </>
      ) : (
        <div className="max-h-64 overflow-auto text-xs text-destructive">
          <Markdown>{output}</Markdown>
        </div>
      )}
    </div>
  )
}

/** `create_chart`: the chart itself when it was drawn (an error comes back as text), and what was asked. */
function ChartStep({ args, output }: { args: Record<string, unknown>; output: string }) {
  let chart: { url?: string; title?: string } | null = null
  try {
    chart = JSON.parse(output)
  } catch {
    // a refusal or a failure: text
  }
  return (
    <div className="flex flex-col gap-2 border-t px-2.5 py-2 text-xs">
      {chart && isBackendImage(chart.url) ? (
        <ChatImage src={chart.url} alt={chart.title} />
      ) : (
        <div className="text-destructive">
          <Markdown>{output}</Markdown>
        </div>
      )}
      <div className="[&_pre]:my-0 [&_pre]:bg-muted/70 [&_pre]:text-[11px]">
        <Markdown>{fenced(JSON.stringify(args, null, 2), 'json')}</Markdown>
      </div>
    </div>
  )
}

const argumentsLine = (args: Record<string, unknown>) =>
  Object.entries(args)
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(' · ')

/** Under an assistant answer: what it was given (files) and how it got there (plan, tool calls). */
export function MessageSources({ trace }: { trace: MessageTrace }) {
  const calls = trace.steps.length
  if (calls === 0 && trace.files.length === 0 && !trace.plan && !trace.usage) return null

  return (
    <details className="group w-full text-xs text-muted-foreground">
      <summary className="flex w-fit cursor-pointer list-none items-center gap-1.5 rounded-full px-2 py-1 select-none hover:bg-muted [&::-webkit-details-marker]:hidden">
        <ChevronRight className="size-3.5 transition-transform group-open:rotate-90" aria-hidden />
        <Wrench className="size-3.5" aria-hidden />
        <span>
          Sources et outils · {calls} appel{calls > 1 ? 's' : ''}
        </span>
      </summary>

      <div className="mt-2 flex flex-col gap-3 rounded-xl border bg-card p-3 text-foreground">
        {trace.plan && (
          <section>
            <h4 className="mb-1 text-xs font-medium text-muted-foreground">Plan</h4>
            <div className="text-xs">
              <Markdown>{trace.plan}</Markdown>
            </div>
          </section>
        )}

        {trace.files.length > 0 && (
          <section>
            <h4 className="mb-1 text-xs font-medium text-muted-foreground">Fichiers à disposition</h4>
            <ul className="flex flex-wrap gap-1.5" aria-label="Fichiers à disposition">
              {trace.files.map((file) => (
                <ScopeChip key={file.id} kind="file" label={file.name} origin={file.collection || undefined} />
              ))}
            </ul>
          </section>
        )}

        {trace.usage && (
          <section>
            <h4 className="mb-1 text-xs font-medium text-muted-foreground">Consommation de tokens</h4>
            <table className="w-full border-collapse text-[11px]">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="py-1 text-left font-medium">Appel</th>
                  <th className="py-1 text-right font-medium">Entrée</th>
                  <th className="py-1 text-right font-medium">Sortie</th>
                  <th className="py-1 text-right font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {trace.usage.calls.map((call, index) => (
                  <tr key={index} className="border-t">
                    <td className="py-1">{nodeLabel(call.node)}</td>
                    <td className="py-1 text-right tabular-nums">{tokens(call.input_tokens)}</td>
                    <td className="py-1 text-right tabular-nums">{tokens(call.output_tokens)}</td>
                    <td className="py-1 text-right tabular-nums">{tokens(call.total_tokens)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t font-medium">
                  <td className="py-1">Total</td>
                  <td className="py-1 text-right tabular-nums">{tokens(trace.usage.input_tokens)}</td>
                  <td className="py-1 text-right tabular-nums">{tokens(trace.usage.output_tokens)}</td>
                  <td className="py-1 text-right tabular-nums">{tokens(trace.usage.total_tokens)}</td>
                </tr>
              </tfoot>
            </table>
          </section>
        )}

        {calls > 0 && (
          <section>
            <h4 className="mb-1 text-xs font-medium text-muted-foreground">Outils utilisés</h4>
            <ol className="flex flex-col gap-1.5">
              {trace.steps.map((step, index) => (
                <li key={index}>
                  <details className="rounded-lg border bg-background">
                    <summary className="flex cursor-pointer items-baseline gap-2 px-2.5 py-1.5 select-none">
                      <span className="shrink-0 font-medium whitespace-nowrap">{toolLabel(step.tool)}</span>
                      <span className="truncate text-muted-foreground">{argumentsLine(step.arguments)}</span>
                    </summary>
                    {step.tool === 'query_data' && typeof step.arguments.sql === 'string' ? (
                      <QueryStep sql={step.arguments.sql} output={step.output} />
                    ) : step.tool === 'create_chart' ? (
                      <ChartStep args={step.arguments} output={step.output} />
                    ) : (
                      <div className="max-h-64 overflow-auto border-t px-2.5 py-2 text-xs [&_pre]:my-0 [&_pre]:bg-muted/70 [&_pre]:text-[11px]">
                        <Markdown>{outputAsMarkdown(step.output)}</Markdown>
                      </div>
                    )}
                  </details>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </details>
  )
}
