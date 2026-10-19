import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

/** The versions of the frontend (compiled in) and of the backend (asked once; null while unknown or if unreachable). */
export function useAppVersion() {
  const [backend, setBackend] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    apiFetch<{ version: string }>('/version').then(
      ({ version }) => !cancelled && setBackend(version),
      () => undefined, // the version is a nicety: never an error for the person
    )
    return () => {
      cancelled = true
    }
  }, [])

  return { frontend: __APP_VERSION__, backend }
}
