import { SidebarTrigger } from '@/components/ui/sidebar'
import type { CollectionSummary } from '@/types/collection'
import type { Message, MessageScope } from '@/types/conversation'
import type { ModelOption } from '@/types/model'
import { ChatInput } from './ChatInput'
import { MessageList } from './MessageList'

interface ChatViewProps {
  conversationId: string | null
  title: string | null
  messages: Message[]
  hasOlder: boolean
  isLoadingOlder: boolean
  onLoadOlder: () => void
  models: ModelOption[]
  modelsLoading: boolean
  modelsError: string | null
  selectedModel: string | null
  onModelChange: (modelId: string) => void
  isAnswering: boolean
  collections: CollectionSummary[]
  onSend: (content: string, scope: MessageScope) => void
  onCancel: () => void
  onCollectionsChanged: () => void
}

export function ChatView({
  conversationId,
  title,
  messages,
  hasOlder,
  isLoadingOlder,
  onLoadOlder,
  models,
  modelsLoading,
  modelsError,
  selectedModel,
  onModelChange,
  isAnswering,
  collections,
  onSend,
  onCancel,
  onCollectionsChanged,
}: ChatViewProps) {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b px-3 py-2">
        <SidebarTrigger />
        <span className="truncate text-sm font-medium">{title ?? 'Nouvelle conversation'}</span>
      </div>

      <MessageList
        conversationId={conversationId}
        messages={messages}
        isAnswering={isAnswering}
        hasOlder={hasOlder}
        isLoadingOlder={isLoadingOlder}
        onLoadOlder={onLoadOlder}
      />

      <ChatInput
        models={models}
        modelsLoading={modelsLoading}
        modelsError={modelsError}
        selectedModel={selectedModel}
        onModelChange={onModelChange}
        isAnswering={isAnswering}
        collections={collections}
        onSend={onSend}
        onCancel={onCancel}
        onCollectionsChanged={onCollectionsChanged}
      />
    </div>
  )
}
