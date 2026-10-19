import { apiFetch, jsonBody } from '@/lib/api'
import type { Conversation, Feedback, Message, MessageScope, Run, RunStatus } from '@/types/conversation'

interface ConversationDto {
  id: string
  title: string
  model: string | null
}

interface MessageDto {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string | null
  collections?: { id: string; name: string }[]
  files?: { id: string; name: string; collection_id: string; collection_name: string }[]
  trace?: {
    plan: string
    files: { file_id: string; file_name: string; collection_name: string }[]
    steps: { tool: string; arguments: Record<string, unknown>; output: string }[]
  } | null
  feedback?: Feedback | null
}

interface RunDto {
  id: string
  status: RunStatus
  error: string | null
}

const toRun = ({ id, status, error }: RunDto): Run => ({ id, status, error })

// system/tool messages and assistant tool-call turns (no text) are plumbing for the agent, not chat bubbles.
const toMessage = (dto: MessageDto): Message[] =>
  (dto.role === 'user' || dto.role === 'assistant') && dto.content
    ? [
        {
          id: dto.id,
          role: dto.role,
          content: dto.content,
          trace: dto.trace
            ? {
                plan: dto.trace.plan,
                files: dto.trace.files.map((f) => ({ id: f.file_id, name: f.file_name, collection: f.collection_name })),
                steps: dto.trace.steps,
              }
            : null,
          feedback: dto.feedback ?? null,
          scope: {
            collections: dto.collections ?? [],
            files: (dto.files ?? []).map((f) => ({
              id: f.id,
              name: f.name,
              collection: { id: f.collection_id, name: f.collection_name },
            })),
          },
        },
      ]
    : []

export const listConversations = async (): Promise<Conversation[]> =>
  (await apiFetch<ConversationDto[]>('/conversations')).map(({ id, title, model }) => ({ id, title, model }))

export const createConversation = async (): Promise<Conversation> => {
  const { id, title, model } = await apiFetch<ConversationDto>('/conversations', {
    method: 'POST',
    body: jsonBody({}),
  })
  return { id, title, model }
}

export const deleteConversation = (id: string) => apiFetch<void>(`/conversations/${id}`, { method: 'DELETE' })

export const MESSAGES_PAGE_SIZE = 30

export interface MessagePage {
  // Oldest first. Only the messages shown as bubbles (see toMessage).
  items: Message[]
  // Older messages exist: ask again with `cursor`.
  hasMore: boolean
  // Id of the oldest message of the page as stored (whether or not it is a bubble): the `before` of the next page.
  cursor: string | null
}

/** The latest page, or the one just before the message `before`. */
export async function listMessages(conversationId: string, before?: string): Promise<MessagePage> {
  const query = new URLSearchParams({ limit: String(MESSAGES_PAGE_SIZE) })
  if (before) query.set('before', before)
  const page = await apiFetch<{ items: MessageDto[]; has_more: boolean }>(
    `/conversations/${conversationId}/messages?${query}`,
  )
  return { items: page.items.flatMap(toMessage), hasMore: page.has_more, cursor: page.items[0]?.id ?? null }
}

/** Stores the user message and queues the assistant's run; the answer arrives later (poll the run). */
export async function sendMessage(
  conversationId: string,
  content: string,
  model?: string,
  scope?: MessageScope,
): Promise<{ messages: Message[]; run: Run }> {
  const sent = await apiFetch<{ message: MessageDto; run: RunDto }>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: jsonBody({
      content,
      model: model ?? null,
      collection_ids: scope?.collections.map((c) => c.id) ?? [],
      file_ids: scope?.files.map((f) => f.id) ?? [],
    }),
  })
  return { messages: toMessage(sent.message), run: toRun(sent.run) }
}

/** Thumbs up/down on an answer; voting again replaces the previous feedback. */
export const putFeedback = (conversationId: string, messageId: string, feedback: Partial<Feedback> & { rating: Feedback['rating'] }) =>
  apiFetch<Feedback>(`/conversations/${conversationId}/messages/${messageId}/feedback`, {
    method: 'PUT',
    body: jsonBody({ rating: feedback.rating, reason: feedback.reason ?? null, comment: feedback.comment ?? null }),
  })

export const deleteFeedback = (conversationId: string, messageId: string) =>
  apiFetch<void>(`/conversations/${conversationId}/messages/${messageId}/feedback`, { method: 'DELETE' })

export const getActiveRun = async (conversationId: string): Promise<Run | null> => {
  const run = await apiFetch<RunDto | null>(`/conversations/${conversationId}/active-run`)
  return run ? toRun(run) : null
}

/** Runs the assistant again on the last message, when it got no answer (no new message is stored). */
export async function retryRun(conversationId: string, model?: string): Promise<Run> {
  return toRun(
    await apiFetch<RunDto>(`/conversations/${conversationId}/runs/retry`, {
      method: 'POST',
      body: jsonBody({ model: model ?? null }),
    }),
  )
}

export const getRun = async (runId: string) => toRun(await apiFetch<RunDto>(`/runs/${runId}`))

export const cancelRun = async (runId: string) => toRun(await apiFetch<RunDto>(`/runs/${runId}/cancel`, { method: 'POST' }))
