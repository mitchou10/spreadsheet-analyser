export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export interface Conversation {
  id: string
  title: string
}

export type RunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Run {
  id: string
  status: RunStatus
  error: string | null
}

export const isRunActive = (run: Run | null): boolean => run?.status === 'queued' || run?.status === 'running'
