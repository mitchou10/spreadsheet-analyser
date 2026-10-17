import { apiFetch, jsonBody } from '@/lib/api'
import type { CollectionSummary, FileAnalysisStatus, SpreadsheetFile } from '@/types/collection'

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
