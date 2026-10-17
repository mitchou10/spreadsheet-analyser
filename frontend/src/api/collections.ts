import { apiFetch, jsonBody } from '@/lib/api'
import type { AnalysisReport, CollectionSummary, FileAnalysisStatus, SpreadsheetFile } from '@/types/collection'

interface CollectionDto {
  id: string
  name: string
  description: string | null
  is_owner: boolean
  file_count: number
}

interface FileDto {
  id: string
  name: string
  size_bytes: number
  uploaded_at: string
  updated_at: string
  status: FileAnalysisStatus
}

const toCollection = (dto: CollectionDto): CollectionSummary => ({
  id: dto.id,
  name: dto.name,
  description: dto.description,
  fileCount: dto.file_count,
  isOwner: dto.is_owner,
})

const toFile = (dto: FileDto): SpreadsheetFile => ({
  id: dto.id,
  name: dto.name,
  sizeBytes: dto.size_bytes,
  uploadedAt: dto.uploaded_at,
  updatedAt: dto.updated_at,
  status: dto.status,
})

export const listCollections = async () => (await apiFetch<CollectionDto[]>('/collections')).map(toCollection)

export const createCollection = async (name: string, description?: string) =>
  toCollection(
    await apiFetch<CollectionDto>('/collections', {
      method: 'POST',
      body: jsonBody({ name, description: description || null }),
    }),
  )

export const listFiles = async (collectionId: string) =>
  (await apiFetch<FileDto[]>(`/collections/${collectionId}/files`)).map(toFile)

export async function uploadFiles(collectionId: string, files: File[]) {
  const form = new FormData()
  for (const file of files) form.append('files', file)
  const uploaded = await apiFetch<FileDto[]>(`/collections/${collectionId}/files`, { method: 'POST', body: form })
  return uploaded.map(toFile)
}

export const deleteFile = (fileId: string) => apiFetch<void>(`/files/${fileId}`, { method: 'DELETE' })

export const retryAnalysis = async (fileId: string) =>
  toFile(await apiFetch<FileDto>(`/files/${fileId}/analysis`, { method: 'POST' }))

export const stopAnalysis = async (fileId: string) =>
  toFile(await apiFetch<FileDto>(`/files/${fileId}/analysis/stop`, { method: 'POST' }))

interface AnalysisDto {
  status: FileAnalysisStatus
  error: string | null
  result: {
    warnings: string[]
    sheets: {
      name: string
      rows: number
      hidden: boolean
      truncated: boolean
      warnings: string[]
      columns: {
        name: string
        type: string
        non_null: number
        null: number
        distinct: number
        distinct_exact: boolean
        numeric?: { min: number | null; max: number | null; mean: number | null }
      }[]
    }[]
  } | null
}

/** Latest analysis of the file's current version; `sheets` is empty until it is ready. */
export async function getAnalysis(fileId: string): Promise<AnalysisReport> {
  const dto = await apiFetch<AnalysisDto>(`/files/${fileId}/analysis`)
  return {
    status: dto.status,
    error: dto.error,
    warnings: dto.result?.warnings ?? [],
    sheets: (dto.result?.sheets ?? []).map((sheet) => ({
      name: sheet.name,
      rows: sheet.rows,
      hidden: sheet.hidden,
      truncated: sheet.truncated,
      warnings: sheet.warnings,
      columns: sheet.columns.map((column) => ({
        name: column.name,
        type: column.type,
        nonNull: column.non_null,
        nulls: column.null,
        distinct: column.distinct,
        distinctExact: column.distinct_exact,
        numeric: column.numeric ?? null,
      })),
    })),
  }
}
