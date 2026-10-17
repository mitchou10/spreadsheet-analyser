import { SidebarTrigger } from '@/components/ui/sidebar'
import type { Message } from '@/types/conversation'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'

interface ChatViewProps {
  title: string | null
  messages: Message[]
  isAnswering: boolean
  onSend: (content: string) => void
  onCancel: () => void
}

export function ChatView({ title, messages, isAnswering, onSend, onCancel }: ChatViewProps) {
  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <SidebarTrigger />
        <span className="truncate text-sm font-medium">{title ?? 'Nouvelle conversation'}</span>
      </div>

      <MessageList messages={messages} isAnswering={isAnswering} />

      <ChatInput isAnswering={isAnswering} onSend={onSend} onCancel={onCancel} />
    </div>
  )
}
