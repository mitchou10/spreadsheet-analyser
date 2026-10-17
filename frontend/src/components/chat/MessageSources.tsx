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
                      <span className="font-medium">{toolLabel(step.tool)}</span>
                      <span className="truncate text-muted-foreground">{argumentsLine(step.arguments)}</span>
                    </summary>
                    <pre className="max-h-64 overflow-auto border-t px-2.5 py-2 text-[11px] leading-snug whitespace-pre-wrap">
                      {pretty(step.output)}
                    </pre>
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
