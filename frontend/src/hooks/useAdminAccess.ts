import { useCallback, useEffect, useState } from 'react'
import * as api from '@/api/admin'
import type { AdminCollection, Person } from '@/types/admin'

/** Every collection and person with their access, plus grant/revoke (admins only: the backend enforces it). */
export function useAdminAccess() {
  const [collections, setCollections] = useState<AdminCollection[]>([])
  const [people, setPeople] = useState<Person[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [collectionList, peopleList] = await Promise.all([api.listCollectionAccess(), api.listPeople()])
      setCollections(collectionList)
      setPeople(peopleList)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Une erreur est survenue')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  /** Runs a change, then reloads both views. Resolves to true when it worked. */
  const change = async (action: () => Promise<unknown>) => {
    try {
      await action()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Une erreur est survenue')
      return false
    }
    await refresh()
    return true
  }

  return {
    collections,
    people,
    isLoading,
    error,
    grant: (collectionId: string, email: string) => change(() => api.grantAccess(collectionId, email)),
    revoke: (collectionId: string, email: string) => change(() => api.revokeAccess(collectionId, email)),
  }
}
