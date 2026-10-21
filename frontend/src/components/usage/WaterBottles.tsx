import { useEffect, useId, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

// There is no published per-token figure. This one comes from Google's 0.26 mL for a median Gemini prompt (a few
// hundred tokens), which counts the cooling on site only: an estimate on the low side (taking the power generation
// into account gives 10x more or higher).
const ML_PER_1K_TOKENS = 0.5
const MAX_BOTTLES = 10

// Inside the bottle (viewBox 0 0 40 100): the water goes from the bottom to just under the neck.
const WATER_BOTTOM = 96
const WATER_TOP = 14
const WATER_RANGE = WATER_BOTTOM - WATER_TOP
const BOTTLE =
  'M15 2 h10 v10 c0 6 9 10 9 22 v58 a6 6 0 0 1 -6 6 h-16 a6 6 0 0 1 -6 -6 v-58 c0 -12 9 -16 9 -22 z'
// Two wave lengths of 40, so sliding it by one wave length loops seamlessly.
const WAVE = 'M0 3 q10 -5 20 0 t20 0 t20 0 t20 0 V12 H0 z'

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** `target` reached progressively (at once when the user asked for less motion). */
function useCountUp(target: number, duration = 1600) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (prefersReducedMotion()) {
      const frame = requestAnimationFrame(() => setValue(target))
      return () => cancelAnimationFrame(frame)
    }
    const start = performance.now()
    let frame = requestAnimationFrame(function tick(now) {
      const progress = Math.min(1, (now - start) / duration)
      setValue(target * (1 - (1 - progress) ** 3))
      if (progress < 1) frame = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(frame)
  }, [target, duration])
  return value
}

function Bottle({ fill, filled, delay }: { fill: number; filled: boolean; delay: number }) {
  const clip = useId()
  // Rises from empty to its level once `filled`; the offset moves the water down from the top of the bottle.
  const offset = filled ? WATER_RANGE * (1 - fill) : WATER_RANGE + 8
  return (
    <svg viewBox="0 0 40 100" className="h-24 w-10 shrink-0" aria-hidden>
      <defs>
        <clipPath id={clip}>
          <path d={BOTTLE} />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clip})`}>
        <g
          style={{
            transform: `translateY(${offset}px)`,
            transition: prefersReducedMotion() ? 'none' : `transform 1600ms cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms`,
          }}
        >
          <g transform={`translate(0 ${WATER_TOP - 3})`}>
            <path d={WAVE} className="water-wave fill-usage-input/80" style={{ animation: 'water-wave 2.4s linear infinite' }} />
            <rect x="0" y="11" width="40" height="100" className="fill-usage-input/80" />
          </g>
        </g>
      </g>
      <path d={BOTTLE} fill="none" strokeWidth="1.5" className="stroke-foreground/50" />
      <rect x="14" y="0" width="12" height="3" rx="1" className="fill-foreground/50" />
    </svg>
  )
}

const formatLiters = (liters: number) =>
  liters >= 1
    ? `${liters.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} L`
    : `${(liters * 1000).toLocaleString('fr-FR', { maximumFractionDigits: liters * 1000 < 10 ? 2 : 0 })} mL`

/** The water the tokens consumed represent, in 1 L bottles that fill up. Mount it with a `key` that changes with the
 * figure to replay the animation. */
export function WaterBottles({ totalTokens, period }: { totalTokens: number; period: string }) {
  const liters = (totalTokens * ML_PER_1K_TOKENS) / 1000 / 1000
  const shownLiters = useCountUp(liters)
  const [filled, setFilled] = useState(false)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setFilled(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  const bottleCount = Math.max(1, Math.ceil(liters))
  const shown = Math.min(bottleCount, MAX_BOTTLES)
  const levels = Array.from({ length: shown }, (_, i) => Math.min(1, Math.max(0, liters - i)))
  const hidden = bottleCount - shown

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Eau consommée · {period}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
          <div className="flex flex-col">
            <span className="text-3xl font-semibold tabular-nums" aria-label={formatLiters(liters)}>
              {formatLiters(shownLiters)}
            </span>
            <span className="text-xs text-muted-foreground">
              {liters >= 1
                ? `soit ${Math.floor(liters).toLocaleString('fr-FR')} bouteille${liters >= 2 ? 's' : ''} de 1 L pleine${liters >= 2 ? 's' : ''}`
                : `${(liters * 100).toLocaleString('fr-FR', { maximumFractionDigits: 2 })} % d’une bouteille de 1 L`}
            </span>
          </div>
          <div className="flex flex-wrap items-end gap-1.5" role="img" aria-label={`${formatLiters(liters)} d’eau en bouteilles de 1 L`}>
            {levels.map((fill, index) => (
              <Bottle key={index} fill={fill} filled={filled} delay={index * 140} />
            ))}
            {hidden > 0 && <span className="pb-2 text-sm text-muted-foreground">+ {hidden.toLocaleString('fr-FR')}</span>}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          Estimation : {ML_PER_1K_TOKENS.toLocaleString('fr-FR')} mL d’eau pour 1 000 tokens (refroidissement des data
          centers uniquement, sans la production d’électricité). Un ordre de grandeur, pas une mesure.
        </p>
      </CardContent>
    </Card>
  )
}
