import { apiFetch, jsonBody } from '@/lib/api'
import type { Conversation, Message, Run, RunStatus } from '@/types/conversation'

interface ConversationDto {
  id: string
  title: string
  model: string | null
}

interface MessageDto {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string | null
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
    ? [{ id: dto.id, role: dto.role, content: dto.content }]
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

export const listMessages = async (conversationId: string): Promise<Message[]> =>
  (await apiFetch<MessageDto[]>(`/conversations/${conversationId}/messages`)).flatMap(toMessage)

/** Stores the user message and queues the assistant's run; the answer arrives later (poll the run). */
export async function sendMessage(conversationId: string, content: string, model?: string): Promise<{ messages: Message[]; run: Run }> {
  const sent = await apiFetch<{ message: MessageDto; run: RunDto }>(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: jsonBody({ content, model: model ?? null }),
  })
  return { messages: toMessage(sent.message), run: toRun(sent.run) }
}

export const getActiveRun = async (conversationId: string): Promise<Run | null> => {
  const run = await apiFetch<RunDto | null>(`/conversations/${conversationId}/active-run`)
  return run ? toRun(run) : null
}

export const getRun = async (runId: string) => toRun(await apiFetch<RunDto>(`/runs/${runId}`))

export const cancelRun = async (runId: string) => toRun(await apiFetch<RunDto>(`/runs/${runId}/cancel`, { method: 'POST' }))
