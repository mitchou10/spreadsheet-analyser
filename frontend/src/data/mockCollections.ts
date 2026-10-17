import type { CollectionSummary } from '../types/collection'

// Placeholder data until the backend exposes a collections API.
export const mockCollections: CollectionSummary[] = [
  {
    id: 'c1',
    name: 'Ventes 2026',
    files: [
      {
        id: 'f1',
        name: 'ventes_q1.xlsx',
        sizeBytes: 245_000,
        uploadedAt: '2026-10-10T09:12:00Z',
        updatedAt: '2026-10-10T09:14:00Z',
        status: 'ready',
      },
      {
        id: 'f2',
        name: 'ventes_q2.xlsx',
        sizeBytes: 198_000,
        uploadedAt: '2026-10-12T14:30:00Z',
        updatedAt: '2026-10-12T14:33:00Z',
        status: 'ready',
      },
      {
        id: 'f3',
        name: 'ventes_q3.xlsx',
        sizeBytes: 312_000,
        uploadedAt: '2026-10-16T08:05:00Z',
        updatedAt: '2026-10-17T10:50:00Z',
        status: 'processing',
      },
      {
        id: 'f4',
        name: 'ventes_q4_brouillon.xlsx',
        sizeBytes: 87_000,
        uploadedAt: '2026-10-17T11:40:00Z',
        updatedAt: '2026-10-17T11:42:00Z',
        status: 'error',
      },
    ],
  },
  {
    id: 'c2',
    name: 'RH - Paie',
    files: [
      {
        id: 'f5',
        name: 'paie_septembre.xlsx',
        sizeBytes: 152_000,
        uploadedAt: '2026-10-01T10:00:00Z',
        updatedAt: '2026-10-01T10:02:00Z',
        status: 'ready',
      },
      {
        id: 'f6',
        name: 'paie_octobre.xlsx',
        sizeBytes: 160_000,
        uploadedAt: '2026-10-17T09:00:00Z',
        updatedAt: '2026-10-17T09:00:00Z',
        status: 'pending',
      },
    ],
  },
  {
    id: 'c3',
    name: 'Budgets',
    files: [],
  },
]
