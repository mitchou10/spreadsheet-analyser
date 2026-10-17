import { Link, Navigate, Route, Routes, useLocation, useMatch, useNavigate } from 'react-router'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { useCollections } from '@/hooks/useCollections'
import { useConversations } from '@/hooks/useConversations'
import { ChatView } from '../chat/ChatView'
import { CollectionDetailView } from '../collections/CollectionDetailView'
import { CollectionsListView } from '../collections/CollectionsListView'
import { AppHeader } from './AppHeader'
import { AppSidebar } from './AppSidebar'

function CollectionNotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
      <p>Cette collection n'existe pas ou vous n'y avez pas accès.</p>
      <Link to="/collections" className="text-foreground underline">
        Retour aux collections
      </Link>
    </div>
  )
}

export function AppShell() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // The URL is the source of truth for what is open: /chat/:conversationId, /collections/:collectionId.
  const activeId = useMatch('/chat/:conversationId')?.params.conversationId ?? null
  const activeCollectionId = useMatch('/collections/:collectionId')?.params.collectionId ?? null

  const chat = useConversations(activeId)
  const backend = useCollections(activeCollectionId)

  const activeConversation = chat.conversations.find((c) => c.id === activeId) ?? null
  const activeCollection = backend.collections.find((c) => c.id === activeCollectionId) ?? null
  const error = chat.error ?? backend.error
  const clearError = chat.error ? chat.clearError : backend.clearError

  const handleSend = async (content: string) => {
    const id = await chat.send(content)
    // First message from the empty /chat page: the conversation now exists, move to its URL.
    if (id && id !== activeId) navigate(`/chat/${id}`)
  }

  const handleDeleteConversation = async (id: string) => {
    await chat.remove(id)
    // Deleting the open conversation leaves its URL dangling: go back to the empty chat.
    if (id === activeId) navigate('/chat', { replace: true })
  }

  const handleFilesSelected = (fileList: globalThis.FileList) => backend.uploadFiles(Array.from(fileList))

  return (
    <div className="flex h-full flex-1 flex-col">
      <AppHeader />
      <SidebarProvider className="min-h-0 flex-1" style={{ transform: 'translateZ(0)' }}>
        <AppSidebar
          conversations={chat.conversations}
          activeId={activeId}
          onSelect={(id) => navigate(`/chat/${id}`)}
          onNewChat={() => navigate('/chat')}
          onDelete={handleDeleteConversation}
          isCollectionsActive={pathname.startsWith('/collections')}
          onShowCollections={() => navigate('/collections')}
        />
        <SidebarInset>
          {error && (
            <div
              role="alert"
              className="flex items-center justify-between gap-2 bg-destructive/10 px-4 py-2 text-sm text-destructive"
            >
              <span>{error}</span>
              <button type="button" className="underline" onClick={clearError}>
                Fermer
              </button>
            </div>
          )}
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route
              path="/chat/:conversationId?"
              element={
                activeId && !chat.isLoading && !activeConversation ? (
                  <Navigate to="/chat" replace />
                ) : (
                  <ChatView title={activeConversation?.title ?? null} messages={chat.messages} onSend={handleSend} />
                )
              }
            />
            <Route
              path="/collections"
              element={
                <CollectionsListView
                  collections={backend.collections}
                  isLoading={backend.isLoading}
                  onSelect={(id) => navigate(`/collections/${id}`)}
                  onCreate={backend.createCollection}
                />
              }
            />
            <Route
              path="/collections/:collectionId"
              element={
                !backend.isLoading && !activeCollection ? (
                  <CollectionNotFound />
                ) : (
                  <CollectionDetailView
                    collection={activeCollection}
                    files={backend.files}
                    isUploading={backend.isUploading}
                    onFilesSelected={handleFilesSelected}
                    onRetry={backend.retryAnalysis}
                    onStop={backend.stopAnalysis}
                    onDelete={backend.deleteFile}
                  />
                )
              }
            />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}

