export interface UsageSums {
  inputTokens: number
  outputTokens: number
  totalTokens: number
  calls: number
}

/** Tokens consumed over the last `days` days, in total and split by what consumed them. */
export interface Usage {
  days: number
  totals: UsageSums
  byNode: (UsageSums & { node: string })[]
  byDay: (UsageSums & { day: string })[]
  byModel: (UsageSums & { model: string | null })[]
  // Administrators only (empty for my own usage).
  byUser: (UsageSums & { userId: string; email: string | null })[]
}
