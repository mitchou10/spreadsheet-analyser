import { useCallback, useEffect, useState } from 'react'
import * as api from '@/api/conversations'
import type { Conversation, Message } from '@/types/conversation'

const messageOf = (error: unknown) => (error instanceof Error ? error.message : 'Une erreur est survenue')

/** Conversations of the current user + the messages of the open one, kept in sync with the backend. */
export function useConversations(activeId: string | null) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  // `loaded` is the conversation `messages` belong to, so a stale list is never shown under another id.
  const [messages, setMessages] = useState<{ loaded: string | null; items: Message[] }>({ loaded: null, items: [] })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async <T>(action: () => Promise<T>): Promise<T | undefined> => {
    try {
      setError(null)
      return await action()
    } catch (e) {
      setError(messageOf(e))
      return undefined
    }
  }, [])

  const refresh = useCallback(() => run(async () => setConversations(await api.listConversations())), [run])

  useEffect(() => {
    refresh().finally(() => setIsLoading(false))
  }, [refresh])

  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    run(async () => {
      const items = await api.listMessages(activeId)
      if (!cancelled) setMessages({ loaded: activeId, items })
    })
    return () => {
      cancelled = true
    }
  }, [activeId, run])

  /** Sends to the open conversation, or starts one first. Resolves to the conversation id (undefined on failure). */
  const send = (content: string) =>
    run(async () => {
      const id = activeId ?? (await api.createConversation()).id
      const sent = await api.sendMessage(id, content)
      setMessages((prev) => ({ loaded: id, items: [...(prev.loaded === id ? prev.items : []), ...sent] }))
      // Refetch: the backend names a new conversation after its first message and re-orders by activity.
      await refresh()
      return id
    })

  const remove = (id: string) =>
    run(async () => {
      await api.deleteConversation(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
    })

  return {
    conversations,
    messages: activeId && messages.loaded === activeId ? messages.items : [],
    isLoading,
    error,
    clearError: () => setError(null),
    send,
    remove,
  }
}
