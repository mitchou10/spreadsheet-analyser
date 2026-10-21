import { useEffect, useState } from 'react'
import * as api from '@/api/usage'
import type { Usage } from '@/types/usage'

/** My token usage, or (`admin`) everyone's / one person's, over the last `days` days. */
export function useUsage(days: number, admin = false, userId: string | null = null) {
  const [result, setResult] = useState<{ key: string; usage: Usage } | { key: string; error: string } | null>(null)
  const key = `${admin}|${days}|${userId}`

  useEffect(() => {
    let cancelled = false
    const request = admin ? api.getAdminUsage(days, userId) : api.getMyUsage(days)
    request
      .then((usage) => !cancelled && setResult({ key, usage }))
      .catch((e) => !cancelled && setResult({ key, error: e instanceof Error ? e.message : 'Une erreur est survenue' }))
    return () => {
      cancelled = true
    }
  }, [key, days, admin, userId])

  const current = result && result.key === key ? result : null
  return {
    usage: current && 'usage' in current ? current.usage : null,
    error: current && 'error' in current ? current.error : null,
    isLoading: current === null,
  }
}
