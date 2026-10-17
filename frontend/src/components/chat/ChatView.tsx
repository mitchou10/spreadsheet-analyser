import { SidebarTrigger } from '@/components/ui/sidebar'
import type { Conversation } from '@/types/conversation'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'

interface ChatViewProps {
  conversation: Conversation | null
  onSend: (content: string) => void
}

export function ChatView({ conversation, onSend }: ChatViewProps) {
  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <SidebarTrigger />
        <span className="truncate text-sm font-medium">{conversation?.title ?? 'Nouvelle conversation'}</span>
      </div>

      <MessageList messages={conversation?.messages ?? []} />

      <ChatInput onSend={onSend} />
    </div>
  )
}
