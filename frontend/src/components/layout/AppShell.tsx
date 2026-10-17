import { Link, Navigate, Route, Routes, useLocation, useMatch, useNavigate } from 'react-router'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { useCollections } from '@/hooks/useCollections'
import { useConversations } from '@/hooks/useConversations'
import { useModels } from '@/hooks/useModels'
import { useCurrentUser } from '@/auth/AuthContext'
import { useState } from 'react'
import { AdminView } from '../admin/AdminView'
import { ChatView } from '../chat/ChatView'
import { CollectionDetailView } from '../collections/CollectionDetailView'
import { CollectionsListView } from '../collections/CollectionsListView'
import { AppHeader } from './AppHeader'
import { AppSidebar } from './AppSidebar'

function Forbidden() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
      <p>Cette page est réservée aux administrateurs.</p>
      <Link to="/chat" className="text-foreground underline">
        Retour au chat
      </Link>
    </div>
  )
}

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
  const { user } = useCurrentUser()
  const { pathname } = useLocation()
  // The URL is the source of truth for what is open: /chat/:conversationId, /collections/:collectionId.
  const activeId = useMatch('/chat/:conversationId')?.params.conversationId ?? null
  const activeCollectionId = useMatch('/collections/:collectionId')?.params.collectionId ?? null

  const chat = useConversations(activeId)
  const modelsList = useModels()
  // A pick only applies to the conversation it was made in (null = the /chat page of a new conversation).
  const [pick, setPick] = useState<{ conversationId: string | null; model: string } | null>(null)
  const backend = useCollections(activeCollectionId)

  const activeConversation = chat.conversations.find((c) => c.id === activeId) ?? null
  const activeCollection = backend.collections.find((c) => c.id === activeCollectionId) ?? null
  // What the selector shows is what is sent: a model the provider no longer lists falls back to the default.
  const isListed = (id: string | null | undefined): id is string => !!id && modelsList.models.some((m) => m.id === id)
  const conversationModel = [activeConversation?.model, modelsList.defaultModel].find(isListed) ?? null
  const selectedModel = pick && pick.conversationId === activeId ? pick.model : conversationModel
  const error = chat.error ?? backend.error
  const clearError = chat.error ? chat.clearError : backend.clearError

  const handleSend = async (content: string) => {
    // Sent with every message: the backend remembers it as the conversation's model.
    const id = await chat.send(content, selectedModel ?? undefined)
    if (id) setPick(null)
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
          isAdminActive={pathname.startsWith('/admin')}
          onShowAdmin={() => navigate('/admin')}
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
                  <ChatView
                    title={activeConversation?.title ?? null}
                    messages={chat.messages}
                    models={modelsList.models}
                    modelsLoading={modelsList.isLoading}
                    modelsError={modelsList.error}
                    selectedModel={selectedModel}
                    onModelChange={(model) => setPick({ conversationId: activeId, model })}
                    isAnswering={chat.isAnswering}
                    onSend={handleSend}
                    onCancel={chat.cancel}
                  />
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
            <Route path="/admin" element={user?.isAdmin ? <AdminView /> : <Forbidden />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        </SidebarInset>
      </SidebarProvider>
    </div>
  )
}
