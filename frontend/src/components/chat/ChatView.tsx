import { SidebarTrigger } from '@/components/ui/sidebar'
import type { Message } from '@/types/conversation'
import type { ModelOption } from '@/types/model'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'

interface ChatViewProps {
  title: string | null
  messages: Message[]
  models: ModelOption[]
  modelsLoading: boolean
  modelsError: string | null
  selectedModel: string | null
  onModelChange: (modelId: string) => void
  isAnswering: boolean
  onSend: (content: string) => void
  onCancel: () => void
}

export function ChatView({
  title,
  messages,
  models,
  modelsLoading,
  modelsError,
  selectedModel,
  onModelChange,
  isAnswering,
  onSend,
  onCancel,
}: ChatViewProps) {
  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <SidebarTrigger />
        <span className="truncate text-sm font-medium">{title ?? 'Nouvelle conversation'}</span>
      </div>

      <MessageList messages={messages} isAnswering={isAnswering} />

      <ChatInput
        models={models}
        modelsLoading={modelsLoading}
        modelsError={modelsError}
        selectedModel={selectedModel}
        onModelChange={onModelChange}
        isAnswering={isAnswering}
        onSend={onSend}
        onCancel={onCancel}
      />
    </div>
  )
}
