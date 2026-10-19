import { useCallback, useLayoutEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { Message } from '@/types/conversation'
import { ArrowDown, Loader2, RotateCcw } from 'lucide-react'
import { MessageBubble } from './MessageBubble'

// Closer than this to the bottom counts as "at the bottom": new messages keep it pinned there.
const BOTTOM_THRESHOLD_PX = 120
// Scrolling this close to the top loads the older page.
const TOP_THRESHOLD_PX = 120

interface MessageListProps {
  conversationId: string | null
  messages: Message[]
  isAnswering: boolean
  hasOlder: boolean
  isLoadingOlder: boolean
  onLoadOlder: () => void
  onRetry: () => void
}

export function MessageList({
  conversationId,
  messages,
  isAnswering,
  hasOlder,
  isLoadingOlder,
  onLoadOlder,
  onRetry,
}: MessageListProps) {
  const scroller = useRef<HTMLDivElement>(null)
  const [atBottom, setAtBottom] = useState(true)
  // What the list looked like at the last layout, to tell "message added at the end" from "older page prepended".
  const previous = useRef<{ conversationId: string | null; first: string | null; last: string | null; height: number }>({
    conversationId: null,
    first: null,
    last: null,
    height: 0,
  })

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    const element = scroller.current
    if (element) element.scrollTo({ top: element.scrollHeight, behavior })
  }, [])

  const first = messages[0]?.id ?? null
  const last = messages[messages.length - 1]?.id ?? null
  const lastIsMine = messages[messages.length - 1]?.role === 'user'
  // The last message got no answer and nothing is running: its run failed or was cancelled.
  const canRetry = lastIsMine && !isAnswering
  // The last answer can be replaced by a new one.
  const lastAnswerId = messages[messages.length - 1]?.role === 'assistant' && !isAnswering ? last : null

  useLayoutEffect(() => {
    const element = scroller.current
    const before = previous.current
    previous.current = { conversationId, first, last, height: element?.scrollHeight ?? 0 }
    if (!element || messages.length === 0) return

    if (before.conversationId !== conversationId || before.last === null) {
      scrollToBottom() // a conversation was just opened: start on its latest message
    } else if (before.first !== first && before.last === last) {
      // Older messages were added above: keep what the reader was looking at where it is.
      element.scrollTop += element.scrollHeight - before.height
    } else if (before.last !== last && (atBottom || lastIsMine)) {
      scrollToBottom('smooth') // a new message at the end, and the reader was following (or sent it)
    }
  }, [conversationId, first, last, messages.length, atBottom, lastIsMine, scrollToBottom])

  // The "thinking" line appears under the last message: keep following it.
  useLayoutEffect(() => {
    if (isAnswering && atBottom) scrollToBottom('smooth')
  }, [isAnswering, atBottom, scrollToBottom])

  const handleScroll = () => {
    const element = scroller.current
    if (!element) return
    setAtBottom(element.scrollHeight - element.scrollTop - element.clientHeight < BOTTOM_THRESHOLD_PX)
    if (element.scrollTop < TOP_THRESHOLD_PX && hasOlder && !isLoadingOlder) onLoadOlder()
  }

  if (messages.length === 0 && !isAnswering) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center text-muted-foreground">
        <p>Posez une question sur votre fichier pour démarrer la conversation.</p>
      </div>
    )
  }

  return (
    <div className="relative min-h-0 flex-1">
      <div ref={scroller} onScroll={handleScroll} className="h-full overflow-y-auto" data-testid="message-scroller">
        <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
          {isLoadingOlder && (
            <p className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
              Chargement des messages précédents…
            </p>
          )}
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              conversationId={conversationId}
              message={message}
              onRegenerate={message.id === lastAnswerId ? onRetry : undefined}
            />
          ))}
          {isAnswering && <p className="animate-pulse text-sm text-muted-foreground">L'assistant réfléchit…</p>}
          {canRetry && (
            <div className="flex items-center justify-end gap-2 text-sm text-muted-foreground">
              <span>L'assistant n'a pas répondu.</span>
              <Button type="button" size="sm" variant="outline" onClick={onRetry}>
                <RotateCcw className="size-3.5" aria-hidden />
                Réessayer
              </Button>
            </div>
          )}
        </div>
      </div>
      {!atBottom && (
        <Button
          type="button"
          size="icon"
          variant="outline"
          className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-background shadow-md"
          aria-label="Aller au dernier message"
          title="Aller au dernier message"
          onClick={() => scrollToBottom('smooth')}
        >
          <ArrowDown className="size-4" />
        </Button>
      )}
    </div>
  )
}
