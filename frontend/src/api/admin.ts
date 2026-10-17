import { apiFetch, jsonBody } from '@/lib/api'
import type { AdminCollection, Person } from '@/types/admin'

interface CollectionDto {
  collection_id: string
  name: string
  description: string | null
  owner_id: string
  owner_email: string | null
  file_count: number
  shared_with: { email: string; granted_by: string; created_at: string }[]
}

interface PersonDto {
  email: string | null
  user_id: string | null
  collections: { collection_id: string; name: string; role: 'owner' | 'viewer' }[]
}

export const listCollectionAccess = async (): Promise<AdminCollection[]> =>
  (await apiFetch<CollectionDto[]>('/admin/collections')).map((dto) => ({
    id: dto.collection_id,
    name: dto.name,
    description: dto.description,
    fileCount: dto.file_count,
    ownerEmail: dto.owner_email,
    ownerId: dto.owner_id,
    sharedWith: dto.shared_with.map((s) => ({ email: s.email, grantedBy: s.granted_by, createdAt: s.created_at })),
  }))

export const listPeople = async (): Promise<Person[]> =>
  (await apiFetch<PersonDto[]>('/admin/people')).map((dto) => ({
    email: dto.email,
    userId: dto.user_id,
    collections: dto.collections.map((c) => ({ collectionId: c.collection_id, name: c.name, role: c.role })),
  }))

export const grantAccess = (collectionId: string, email: string) =>
  apiFetch<unknown>(`/admin/collections/${collectionId}/access`, { method: 'POST', body: jsonBody({ email }) })

export const revokeAccess = (collectionId: string, email: string) =>
  apiFetch<void>(`/admin/collections/${collectionId}/access/${encodeURIComponent(email)}`, { method: 'DELETE' })
