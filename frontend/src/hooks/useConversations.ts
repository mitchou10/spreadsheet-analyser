import { useCallback, useEffect, useState } from 'react'
import * as api from '@/api/conversations'
import { isRunActive, type Conversation, type Message, type MessageScope, type Run } from '@/types/conversation'

const POLL_INTERVAL_MS = 1000

interface MessagesState {
  loaded: string | null
  // Oldest first: the newest page, plus the older pages loaded while scrolling up.
  items: Message[]
  hasMore: boolean
  // `before` of the next (older) page.
  cursor: string | null
}

/** The latest page replaces the newest part of what is loaded; the older pages already loaded are kept. */
function mergeLatest(current: MessagesState, conversationId: string, latest: api.MessagePage): MessagesState {
  if (current.loaded !== conversationId || current.items.length === 0) {
    return { loaded: conversationId, items: latest.items, hasMore: latest.hasMore, cursor: latest.cursor }
  }
  const latestIds = new Set(latest.items.map((m) => m.id))
  const overlap = current.items.findIndex((m) => latestIds.has(m.id))
  const older = overlap === -1 ? current.items : current.items.slice(0, overlap)
  return { ...current, items: [...older, ...latest.items] }
}

const messageOf = (error: unknown) => (error instanceof Error ? error.message : 'Une erreur est survenue')

/** Conversations of the current user + the messages and in-flight assistant run of the open one. */
export function useConversations(activeId: string | null) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  // `loaded` is the conversation `messages` belong to, so a stale list is never shown under another id.
  const [messages, setMessages] = useState<MessagesState>({ loaded: null, items: [], hasMore: false, cursor: null })
  const [isLoadingOlder, setIsLoadingOlder] = useState(false)
  const [run, setRun] = useState<{ conversationId: string; run: Run } | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const run_ = useCallback(async <T>(action: () => Promise<T>): Promise<T | undefined> => {
    try {
      setError(null)
      return await action()
    } catch (e) {
      setError(messageOf(e))
      return undefined
    }
  }, [])

  const refresh = useCallback(() => run_(async () => setConversations(await api.listConversations())), [run_])

  useEffect(() => {
    refresh().finally(() => setIsLoading(false))
  }, [refresh])

  // Opening a conversation: load its messages, and resume waiting for a run that was still in progress.
  useEffect(() => {
    if (!activeId) return
    let cancelled = false
    run_(async () => {
      const [page, activeRun] = await Promise.all([api.listMessages(activeId), api.getActiveRun(activeId)])
      if (cancelled) return
      setMessages({ loaded: activeId, items: page.items, hasMore: page.hasMore, cursor: page.cursor })
      setRun((prev) => (activeRun ? { conversationId: activeId, run: activeRun } : prev?.conversationId === activeId ? null : prev))
    })
    return () => {
      cancelled = true
    }
  }, [activeId, run_])

  // The assistant answers asynchronously (worker): poll the run, then fetch the reply it stored.
  const pendingRun = run && isRunActive(run.run) ? run : null
  useEffect(() => {
    if (!pendingRun) return
    const { conversationId, run: current } = pendingRun
    const timer = setInterval(async () => {
      try {
        const latest = await api.getRun(current.id)
        if (isRunActive(latest)) return
        clearInterval(timer)
        setRun(null)
        if (latest.status === 'failed') setError(latest.error ?? "L'assistant n'a pas pu répondre")
        if (latest.status !== 'cancelled') {
          const latestPage = await api.listMessages(conversationId)
          setMessages((prev) => mergeLatest(prev, conversationId, latestPage))
        }
        refresh()
      } catch (e) {
        clearInterval(timer)
        setRun(null)
        setError(messageOf(e))
      }
    }, POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [pendingRun?.run.id, refresh]) // eslint-disable-line react-hooks/exhaustive-deps

  /** Sends to the open conversation, or starts one first. Resolves to the conversation id (undefined on failure). */
  const send = (content: string, model?: string, scope?: MessageScope) =>
    run_(async () => {
      const id = activeId ?? (await api.createConversation()).id
      const sent = await api.sendMessage(id, content, model, scope)
      setMessages((prev) =>
        prev.loaded === id
          ? { ...prev, items: [...prev.items, ...sent.messages] }
          : { loaded: id, items: sent.messages, hasMore: false, cursor: sent.messages[0]?.id ?? null },
      )
      setRun({ conversationId: id, run: sent.run })
      // Refetch: the backend names a new conversation after its first message.
      await refresh()
      return id
    })

  /** Scrolling up: prepend the page of messages before the oldest one loaded. */
  const loadOlder = async () => {
    if (!activeId || isLoadingOlder || messages.loaded !== activeId || !messages.hasMore || !messages.cursor) return
    setIsLoadingOlder(true)
    await run_(async () => {
      const page = await api.listMessages(activeId, messages.cursor ?? undefined)
      setMessages((prev) =>
        prev.loaded === activeId
          ? { ...prev, items: [...page.items, ...prev.items], hasMore: page.hasMore, cursor: page.cursor ?? prev.cursor }
          : prev,
      )
    })
    setIsLoadingOlder(false)
  }

  const cancel = () =>
    run_(async () => {
      if (!pendingRun) return
      await api.cancelRun(pendingRun.run.id)
      setRun(null)
    })

  const remove = (id: string) =>
    run_(async () => {
      await api.deleteConversation(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      setRun((prev) => (prev?.conversationId === id ? null : prev))
    })

  return {
    conversations,
    messages: activeId && messages.loaded === activeId ? messages.items : [],
    hasOlder: activeId !== null && messages.loaded === activeId && messages.hasMore,
    isLoadingOlder,
    loadOlder,
    // True while the assistant is answering the open conversation.
    isAnswering: pendingRun !== null && pendingRun.conversationId === activeId,
    isLoading,
    error,
    clearError: () => setError(null),
    send,
    cancel,
    remove,
  }
}
