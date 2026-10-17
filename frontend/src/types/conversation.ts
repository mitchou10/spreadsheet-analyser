import type { FileAnalysisStatus } from './collection'

/** How an assistant answer was produced: what it was given and what it looked up. */
export interface MessageTrace {
  plan: string
  files: { id: string; name: string; collection: string }[]
  steps: { tool: string; arguments: Record<string, unknown>; output: string }[]
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  // What a user question was aimed at (empty = everything the user could read).
  scope: MessageScope
  // Assistant answers only (null for older answers and for user messages).
  trace: MessageTrace | null
}

export interface Conversation {
  id: string
  title: string
  // Model chosen for this conversation; null = the backend's default.
  model: string | null
}

/** What a question is about: whole collections and/or specific files. Empty = everything I can read. */
export interface MessageScope {
  collections: { id: string; name: string }[]
  // A file keeps the collection it comes from, so it can be shown next to its name.
  // `status` is only known for a file imported from the composer, whose analysis the composer waits for.
  files: { id: string; name: string; collection: { id: string; name: string }; status?: FileAnalysisStatus }[]
}

export const emptyScope: MessageScope = { collections: [], files: [] }

export type RunStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Run {
  id: string
  status: RunStatus
  error: string | null
}

export const isRunActive = (run: Run | null): boolean => run?.status === 'queued' || run?.status === 'running'
