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

export interface ColumnReport {
  name: string
  type: string
  nonNull: number
  nulls: number
  distinct: number
  distinctExact: boolean
  numeric: { min: number | null; max: number | null; mean: number | null } | null
}

export interface SheetReport {
  name: string
  rows: number
  hidden: boolean
  truncated: boolean
  columns: ColumnReport[]
  warnings: string[]
}

export interface AnalysisReport {
  status: FileAnalysisStatus
  error: string | null
  sheets: SheetReport[]
  warnings: string[]
}
