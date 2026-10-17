import { ScrollArea } from '@/components/ui/scroll-area'
import type { Message } from '@/types/conversation'
import { MessageBubble } from './MessageBubble'

export function MessageList({ messages }: { messages: Message[] }) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Posez une question sur votre fichier pour démarrer la conversation.</p>
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex max-w-3xl flex-col gap-6 px-4 py-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
      </div>
    </ScrollArea>
  )
}
