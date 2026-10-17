import { apiFetch, jsonBody } from '@/lib/api'
import type { Conversation, Message } from '@/types/conversation'

interface ConversationDto {
  id: string
  title: string
}

interface MessageDto {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string | null
}

// system/tool messages and assistant tool-call turns (no text) are plumbing for the agent, not chat bubbles.
const toMessage = (dto: MessageDto): Message[] =>
  (dto.role === 'user' || dto.role === 'assistant') && dto.content
    ? [{ id: dto.id, role: dto.role, content: dto.content }]
    : []

export const listConversations = async (): Promise<Conversation[]> =>
  (await apiFetch<ConversationDto[]>('/conversations')).map(({ id, title }) => ({ id, title }))

export const createConversation = async (): Promise<Conversation> => {
  const { id, title } = await apiFetch<ConversationDto>('/conversations', { method: 'POST', body: jsonBody({}) })
  return { id, title }
}

export const deleteConversation = (id: string) => apiFetch<void>(`/conversations/${id}`, { method: 'DELETE' })

export const listMessages = async (conversationId: string): Promise<Message[]> =>
  (await apiFetch<MessageDto[]>(`/conversations/${conversationId}/messages`)).flatMap(toMessage)

export const sendMessage = async (conversationId: string, content: string): Promise<Message[]> =>
  toMessage(
    await apiFetch<MessageDto>(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: jsonBody({ content }),
    }),
  )
