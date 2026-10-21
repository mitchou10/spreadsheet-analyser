import { apiFetch } from '@/lib/api'
import type { Usage, UsageSums } from '@/types/usage'

interface SumsDto {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  calls: number
}

interface UsageDto {
  days: number
  totals: SumsDto
  by_node: (SumsDto & { node: string })[]
  by_day: (SumsDto & { day: string })[]
  by_model: (SumsDto & { model: string | null })[]
  by_user: (SumsDto & { user_id: string; email: string | null })[]
}

const toSums = (dto: SumsDto): UsageSums => ({
  inputTokens: dto.input_tokens,
  outputTokens: dto.output_tokens,
  totalTokens: dto.total_tokens,
  calls: dto.calls,
})

const toUsage = (dto: UsageDto): Usage => ({
  days: dto.days,
  totals: toSums(dto.totals),
  byNode: dto.by_node.map((r) => ({ ...toSums(r), node: r.node })),
  byDay: dto.by_day.map((r) => ({ ...toSums(r), day: r.day })),
  byModel: dto.by_model.map((r) => ({ ...toSums(r), model: r.model })),
  byUser: dto.by_user.map((r) => ({ ...toSums(r), userId: r.user_id, email: r.email })),
})

export const getMyUsage = async (days: number): Promise<Usage> => toUsage(await apiFetch<UsageDto>(`/usage/me?days=${days}`))

/** Everyone's usage (administrators), or only `userId`'s. */
export const getAdminUsage = async (days: number, userId?: string | null): Promise<Usage> =>
  toUsage(await apiFetch<UsageDto>(`/admin/usage?days=${days}${userId ? `&user_id=${encodeURIComponent(userId)}` : ''}`))
