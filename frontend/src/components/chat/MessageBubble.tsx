import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Message } from '@/types/conversation'
import { Bot, RotateCcw, User } from 'lucide-react'
import { Markdown } from './Markdown'
import { MessageSources } from './MessageSources'
import { ScopeChip } from './ScopeChip'

interface MessageBubbleProps {
  message: Message
  // Given only for the last answer: replaces it by a new one.
  onRegenerate?: () => void
}

export function MessageBubble({ message, onRegenerate }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const hasSources = message.scope.collections.length > 0 || message.scope.files.length > 0

  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <div
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground',
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div className={cn('flex max-w-[75%] flex-col gap-1.5', isUser && 'items-end')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
            isUser && 'whitespace-pre-wrap',
            isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
          )}
        >
          {isUser ? message.content : <Markdown>{message.content}</Markdown>}
        </div>
        {!isUser && message.trace && <MessageSources trace={message.trace} />}
        {onRegenerate && (
          <Button type="button" size="sm" variant="ghost" className="text-muted-foreground" onClick={onRegenerate}>
            <RotateCcw className="size-3.5" aria-hidden />
            Régénérer
          </Button>
        )}
        {isUser && hasSources && (
          <ul className="flex flex-wrap justify-end gap-1.5" aria-label="Sources de la question">
            {message.scope.collections.map((c) => (
              <ScopeChip key={c.id} kind="collection" label={c.name} />
            ))}
            {message.scope.files.map((f) => (
              <ScopeChip key={f.id} kind="file" label={f.name} origin={f.collection.name} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
