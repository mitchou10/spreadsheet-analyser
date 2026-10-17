export interface AccessEntry {
  email: string
  grantedBy: string
  createdAt: string
}

export interface AdminCollection {
  id: string
  name: string
  description: string | null
  fileCount: number
  // null for collections created before owner emails were recorded.
  ownerEmail: string | null
  ownerId: string
  sharedWith: AccessEntry[]
}

export interface PersonCollection {
  collectionId: string
  name: string
  role: 'owner' | 'viewer'
}

export interface Person {
  email: string | null
  userId: string | null
  collections: PersonCollection[]
}
