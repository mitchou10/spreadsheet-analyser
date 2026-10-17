import { apiFetch } from '@/lib/api'
import type { ModelOption } from '@/types/model'

interface ModelsDto {
  default: string
  models: { id: string; owned_by: string | null }[]
}

/** Chat-capable models. The first call can take a while: the backend tests each model, then caches the result. */
export async function listModels(): Promise<{ defaultModel: string; models: ModelOption[] }> {
  const dto = await apiFetch<ModelsDto>('/models')
  return { defaultModel: dto.default, models: dto.models.map((m) => ({ id: m.id, ownedBy: m.owned_by })) }
}
