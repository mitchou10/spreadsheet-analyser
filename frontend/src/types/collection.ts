export type FileAnalysisStatus = 'pending' | 'processing' | 'ready' | 'error' | 'stopped'

export interface SpreadsheetFile {
  id: string
  name: string
  sizeBytes: number
  uploadedAt: string
  updatedAt: string
  status: FileAnalysisStatus
}

export interface CollectionSummary {
  id: string
  name: string
  description: string | null
  fileCount: number
  // False when the collection was shared with me: read-only.
  isOwner: boolean
}
