import { useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { ModelOption } from '@/types/model'
import { ModelSelector } from './ModelSelector'
import { ArrowUp, Square } from 'lucide-react'

interface ChatInputProps {
  models: ModelOption[]
  modelsLoading: boolean
  modelsError: string | null
  selectedModel: string | null
  onModelChange: (modelId: string) => void
  isAnswering: boolean
  onSend: (content: string) => void
  onCancel: () => void
}

export function ChatInput({ models, modelsLoading, modelsError, selectedModel, onModelChange, isAnswering, onSend, onCancel }: ChatInputProps) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || isAnswering) return
    onSend(trimmed)
    setValue('')
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t bg-background px-4 py-4">
      <div className="mx-auto flex max-w-3xl flex-col gap-2">
        <ModelSelector
          models={models}
          isLoading={modelsLoading}
          error={modelsError}
          value={selectedModel}
          onChange={onModelChange}
        />
        <div className="flex items-end gap-2">
          <Textarea
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Écrivez votre message…"
            rows={1}
            className="max-h-40 min-h-11 resize-none"
          />
          {isAnswering ? (
            <Button size="icon" variant="outline" aria-label="Arrêter la réponse" onClick={onCancel}>
              <Square className="size-4" />
            </Button>
          ) : (
            <Button size="icon" aria-label="Envoyer" onClick={submit} disabled={!value.trim()}>
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
