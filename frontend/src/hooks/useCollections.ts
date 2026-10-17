import { useCallback, useEffect, useState } from 'react'
import * as api from '@/api/collections'
import type { CollectionSummary, SpreadsheetFile } from '@/types/collection'

const POLL_INTERVAL_MS = 5000
const IN_PROGRESS: SpreadsheetFile['status'][] = ['pending', 'processing']

const messageOf = (error: unknown) => (error instanceof Error ? error.message : 'Une erreur est survenue')

/** Collections of the current user + the files of the one being viewed, kept in sync with the backend. */
export function useCollections(activeCollectionId: string | null) {
  const [collections, setCollections] = useState<CollectionSummary[]>([])
  const [files, setFiles] = useState<SpreadsheetFile[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isUploading, setIsUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async <T>(action: () => Promise<T>): Promise<T | undefined> => {
    try {
      setError(null)
      return await action()
    } catch (e) {
      setError(messageOf(e))
      return undefined
    }
  }, [])

  const refreshCollections = useCallback(
    () => run(async () => setCollections(await api.listCollections())),
    [run],
  )

  const refreshFiles = useCallback(
    (collectionId: string) => run(async () => setFiles(await api.listFiles(collectionId))),
    [run],
  )

  useEffect(() => {
    refreshCollections().finally(() => setIsLoading(false))
  }, [refreshCollections])

  useEffect(() => {
    setFiles([])
    if (activeCollectionId) refreshFiles(activeCollectionId)
  }, [activeCollectionId, refreshFiles])

  // Analyses run asynchronously: keep polling while any file of the open collection is still in progress.
  const hasInProgress = files.some((file) => IN_PROGRESS.includes(file.status))
  useEffect(() => {
    if (!activeCollectionId || !hasInProgress) return
    const timer = setInterval(() => refreshFiles(activeCollectionId), POLL_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [activeCollectionId, hasInProgress, refreshFiles])

  const createCollection = (name: string, description?: string) =>
    run(async () => {
      const created = await api.createCollection(name, description)
      setCollections((prev) => [created, ...prev])
      return created
    })

  const uploadFiles = async (selected: File[]) => {
    if (!activeCollectionId) return
    setIsUploading(true)
    await run(async () => {
      await api.uploadFiles(activeCollectionId, selected)
      await Promise.all([refreshFiles(activeCollectionId), refreshCollections()])
    })
    setIsUploading(false)
  }

  const replaceFile = (updated: SpreadsheetFile) =>
    setFiles((prev) => prev.map((file) => (file.id === updated.id ? updated : file)))

  const retryAnalysis = (fileId: string) => run(async () => replaceFile(await api.retryAnalysis(fileId)))

  const stopAnalysis = (fileId: string) => run(async () => replaceFile(await api.stopAnalysis(fileId)))

  const deleteFile = (fileId: string) =>
    run(async () => {
      await api.deleteFile(fileId)
      setFiles((prev) => prev.filter((file) => file.id !== fileId))
      await refreshCollections()
    })

  return {
    collections,
    files,
    isLoading,
    isUploading,
    error,
    clearError: () => setError(null),
    createCollection,
    uploadFiles,
    retryAnalysis,
    stopAnalysis,
    deleteFile,
  }
}
