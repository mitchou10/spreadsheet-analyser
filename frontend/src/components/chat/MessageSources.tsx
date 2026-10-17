import type { MessageTrace } from '@/types/conversation'
import { ChevronRight, Wrench } from 'lucide-react'
import { ScopeChip } from './ScopeChip'

// The agent's tools (agent-worker/app/agent/tools.py), named for people.
const TOOL_LABELS: Record<string, string> = {
  list_files: 'Liste des fichiers',
  search: 'Recherche de colonnes',
  search_values: 'Recherche de valeurs',
  describe_sheet: 'Détail d’une feuille',
  describe_column: 'Détail d’une colonne',
  query_data: 'Requête SQL',
  account_overview: 'Vue d’ensemble du compte',
  account_files: 'Fichiers du compte',
}

const toolLabel = (tool: string) => TOOL_LABELS[tool] ?? tool

/** The tool's output is JSON for the agent: show it indented when it parses, as is otherwise (errors are text). */
function pretty(output: string): string {
  try {
    return JSON.stringify(JSON.parse(output), null, 2)
  } catch {
    return output
  }
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
      <pre className="overflow-auto rounded-md bg-muted/60 p-2 text-[11px] leading-snug whitespace-pre-wrap">{sql}</pre>
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
        <pre className="max-h-64 overflow-auto text-[11px] leading-snug whitespace-pre-wrap text-destructive">{output}</pre>
      )}
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
  if (calls === 0 && trace.files.length === 0 && !trace.plan) return null

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
            <p className="text-xs whitespace-pre-wrap">{trace.plan}</p>
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
                    ) : (
                      <pre className="max-h-64 overflow-auto border-t px-2.5 py-2 text-[11px] leading-snug whitespace-pre-wrap">
                        {pretty(step.output)}
                      </pre>
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
