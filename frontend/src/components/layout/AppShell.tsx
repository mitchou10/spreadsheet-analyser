import { useState } from 'react'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { mockCollections } from '@/data/mockCollections'
import { mockConversations } from '@/data/mockConversations'
import type { SpreadsheetFile } from '@/types/collection'
import type { Message } from '@/types/conversation'
import { ChatView } from '../chat/ChatView'
import { CollectionDetailView } from '../collections/CollectionDetailView'
import { CollectionsListView } from '../collections/CollectionsListView'
import { AppHeader } from './AppHeader'
import { AppSidebar } from './AppSidebar'

type View = 'chat' | 'collections' | 'collection-detail'

export function AppShell() {
  const [conversations, setConversations] = useState(mockConversations)
  const [activeId, setActiveId] = useState<string | null>(conversations[0]?.id ?? null)
  const [collections, setCollections] = useState(mockCollections)
  const [activeCollectionId, setActiveCollectionId] = useState<string | null>(null)
  const [view, setView] = useState<View>('chat')

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null
  const activeCollection = collections.find((c) => c.id === activeCollectionId) ?? null

  const handleNewChat = () => {
    const id = crypto.randomUUID()
    setConversations((prev) => [{ id, title: 'Nouvelle conversation', messages: [] }, ...prev])
    setActiveId(id)
    setView('chat')
  }

  const handleSelectConversation = (id: string) => {
    setActiveId(id)
    setView('chat')
  }

  const handleSelectCollection = (id: string) => {
    setActiveCollectionId(id)
    setView('collection-detail')
  }

  const handleFilesSelected = (fileList: globalThis.FileList) => {
    if (!activeCollectionId) return
    const now = new Date().toISOString()
    const newFiles: SpreadsheetFile[] = Array.from(fileList).map((file) => ({
      id: crypto.randomUUID(),
      name: file.name,
      sizeBytes: file.size,
      uploadedAt: now,
      updatedAt: now,
      status: 'pending',
    }))
    setCollections((prev) =>
      prev.map((c) => (c.id === activeCollectionId ? { ...c, files: [...c.files, ...newFiles] } : c)),
    )
  }

  const updateFileStatus = (fileId: string, status: SpreadsheetFile['status']) => {
    setCollections((prev) =>
      prev.map((c) => ({
        ...c,
        files: c.files.map((f) => (f.id === fileId ? { ...f, status, updatedAt: new Date().toISOString() } : f)),
      })),
    )
  }

  const handleRetryAnalysis = (fileId: string) => updateFileStatus(fileId, 'processing')

  const handleStopAnalysis = (fileId: string) => updateFileStatus(fileId, 'stopped')

  const handleDeleteFile = (fileId: string) => {
    setCollections((prev) => prev.map((c) => ({ ...c, files: c.files.filter((f) => f.id !== fileId) })))
  }

  const handleSend = (content: string) => {
    if (!activeId) return
    const message: Message = { id: crypto.randomUUID(), role: 'user', content }
    setConversations((prev) =>
      prev.map((c) => (c.id === activeId ? { ...c, messages: [...c.messages, message] } : c)),
    )
  }

  return (
    <div className="flex h-full flex-1 flex-col">
      <AppHeader />
      <SidebarProvider className="min-h-0 flex-1" style={{ transform: 'translateZ(0)' }}>
        <AppSidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={handleSelectConversation}
          onNewChat={handleNewChat}
          isCollectionsActive={view !== 'chat'}
          onShowCollections={() => setView('collections')}
        />
        <SidebarInset>
          {view === 'collections' && (
            <CollectionsListView collections={collections} onSelect={handleSelectCollection} />
          )}
          {view === 'collection-detail' && (
            <CollectionDetailView
              collection={activeCollection}
              onFilesSelected={handleFilesSelected}
              onRetry={handleRetryAnalysis}
              onStop={handleStopAnalysis}
              onDelete={handleDeleteFile}
            />
          )}
          {view === 'chat' && <ChatView conversation={activeConversation} onSend={handleSend} />}
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}

