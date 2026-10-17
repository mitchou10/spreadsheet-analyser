import { useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { ArrowUp } from 'lucide-react'

interface ChatInputProps {
  onSend: (content: string) => void
}

export function ChatInput({ onSend }: ChatInputProps) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed) return
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
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <Textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Écrivez votre message…"
          rows={1}
          className="max-h-40 min-h-11 resize-none"
        />
        <Button size="icon" onClick={submit} disabled={!value.trim()}>
          <ArrowUp className="size-4" />
        </Button>
      </div>
    </div>
  )
}
