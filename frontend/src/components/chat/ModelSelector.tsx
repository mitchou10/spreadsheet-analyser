import type { ModelOption } from '@/types/model'
import { Cpu } from 'lucide-react'

interface ModelSelectorProps {
  models: ModelOption[]
  isLoading: boolean
  error: string | null
  value: string | null
  onChange: (modelId: string) => void
}

export function ModelSelector({ models, isLoading, error, value, onChange }: ModelSelectorProps) {
  if (isLoading) {
    return <span className="animate-pulse text-xs text-muted-foreground">Chargement des modèles…</span>
  }
  if (error || models.length === 0) {
    // Chat still works: the backend falls back to its default model.
    return (
      <span className="text-xs text-muted-foreground" title={error ?? undefined}>
        Modèle par défaut
      </span>
    )
  }

  return (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <Cpu className="size-3.5" aria-hidden />
      <span className="sr-only">Modèle</span>
      <select
        value={value ?? ''}
        onChange={(event) => onChange(event.target.value)}
        className="h-7 max-w-56 truncate rounded-md border border-input bg-transparent px-2 text-xs text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/50 dark:bg-input/30"
      >
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.id}
          </option>
        ))}
      </select>
    </label>
  )
}
