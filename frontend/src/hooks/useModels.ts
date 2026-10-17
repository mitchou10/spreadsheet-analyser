import { useEffect, useState } from 'react'
import { listModels } from '@/api/models'
import type { ModelOption } from '@/types/model'

interface ModelsState {
  models: ModelOption[]
  defaultModel: string | null
  isLoading: boolean
  error: string | null
}

/** The models the assistant can use, loaded once (the backend caches the capability tests). */
export function useModels(): ModelsState {
  const [state, setState] = useState<ModelsState>({ models: [], defaultModel: null, isLoading: true, error: null })

  useEffect(() => {
    let cancelled = false
    listModels()
      .then(({ defaultModel, models }) => {
        if (!cancelled) setState({ models, defaultModel, isLoading: false, error: null })
      })
      .catch((e: unknown) => {
        if (!cancelled)
          setState({
            models: [],
            defaultModel: null,
            isLoading: false,
            error: e instanceof Error ? e.message : 'Impossible de charger les modèles',
          })
      })
    return () => {
      cancelled = true
    }
  }, [])

  return state
}
