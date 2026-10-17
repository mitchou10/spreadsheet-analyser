import { useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { ModelOption } from '@/types/model'
import { ModelSelector } from './ModelSelector'
import { ScopePicker } from './ScopePicker'
import { ScopeChip } from './ScopeChip'
import type { CollectionSummary } from '@/types/collection'
import { emptyScope, type MessageScope } from '@/types/conversation'
import { ArrowUp, Square } from 'lucide-react'

interface ChatInputProps {
  models: ModelOption[]
  modelsLoading: boolean
  modelsError: string | null
  selectedModel: string | null
  onModelChange: (modelId: string) => void
  isAnswering: boolean
  collections: CollectionSummary[]
  onSend: (content: string, scope: MessageScope) => void
  onCancel: () => void
}

export function ChatInput({ models, modelsLoading, modelsError, selectedModel, onModelChange, isAnswering, collections, onSend, onCancel }: ChatInputProps) {
  const [value, setValue] = useState('')
  // The scope belongs to the next message only: it is cleared once sent.
  const [scope, setScope] = useState<MessageScope>(emptyScope)

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || isAnswering) return
    onSend(trimmed, scope)
    setValue('')
    setScope(emptyScope)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const hasScope = scope.collections.length > 0 || scope.files.length > 0

  return (
    <div className="bg-background px-4 pt-2 pb-4">
      <div className="mx-auto max-w-3xl rounded-3xl border bg-card px-3 pt-2.5 pb-2 shadow-sm focus-within:ring-2 focus-within:ring-ring/30">
        {hasScope && (
          <ul className="mb-2 flex flex-wrap gap-1.5 px-1" aria-label="Périmètre de la question">
            {scope.collections.map((c) => (
              <ScopeChip
                key={c.id}
                kind="collection"
                label={c.name}
                onRemove={() => setScope({ ...scope, collections: scope.collections.filter((x) => x.id !== c.id) })}
              />
            ))}
            {scope.files.map((f) => (
              <ScopeChip
                key={f.id}
                kind="file"
                label={f.name}
                origin={f.collection.name}
                onRemove={() => setScope({ ...scope, files: scope.files.filter((x) => x.id !== f.id) })}
              />
            ))}
          </ul>
        )}
        <Textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Posez une question sur vos fichiers…"
          rows={1}
          className="max-h-40 min-h-10 resize-none border-0 bg-transparent px-1 py-1.5 shadow-none focus-visible:border-0 focus-visible:ring-0 dark:bg-transparent"
        />
        <div className="mt-1 flex items-center gap-1">
          <ScopePicker collections={collections} scope={scope} onChange={setScope} disabled={isAnswering} />
          <ModelSelector
            models={models}
            isLoading={modelsLoading}
            error={modelsError}
            value={selectedModel}
            onChange={onModelChange}
          />
          <div className="ml-auto">
            {isAnswering ? (
              <Button size="icon" variant="outline" className="rounded-full" aria-label="Arrêter la réponse" onClick={onCancel}>
                <Square className="size-4" />
              </Button>
            ) : (
              <Button size="icon" className="rounded-full" aria-label="Envoyer" onClick={submit} disabled={!value.trim()}>
                <ArrowUp className="size-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
