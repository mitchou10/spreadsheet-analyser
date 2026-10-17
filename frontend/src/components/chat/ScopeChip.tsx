import { cn } from '@/lib/utils'
import type { FileAnalysisStatus } from '@/types/collection'
import { AlertCircle, FileSpreadsheet, Folder, Loader2, X } from 'lucide-react'

interface ScopeChipProps {
  kind: 'collection' | 'file'
  label: string
  // The collection a file comes from.
  origin?: string
  // Analysis state of a file just imported: shown while it is not ready.
  status?: FileAnalysisStatus
  // Present while the chip can be edited (the composer); absent on a sent message.
  onRemove?: () => void
}

const STATUS_TEXT: Partial<Record<FileAnalysisStatus, string>> = {
  pending: 'Analyse en attente…',
  processing: 'Analyse en cours…',
  error: 'Analyse en erreur',
  stopped: 'Analyse arrêtée',
}

export function ScopeChip({ kind, label, origin, status, onRemove }: ScopeChipProps) {
  const busy = status === 'pending' || status === 'processing'
  const failed = status === 'error' || status === 'stopped'
  const Icon = kind === 'collection' ? Folder : FileSpreadsheet
  return (
    <li
      className={cn('flex max-w-72 items-center gap-1.5 rounded-full bg-muted py-1 pl-2.5 text-xs', onRemove ? 'pr-1.5' : 'pr-2.5')}
      title={[origin ? `${origin} / ${label}` : label, status && STATUS_TEXT[status]].filter(Boolean).join(' — ')}
    >
      {busy ? (
        <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden />
      ) : failed ? (
        <AlertCircle className="size-3.5 shrink-0 text-destructive" aria-hidden />
      ) : (
        <Icon className="size-3.5 shrink-0" aria-hidden />
      )}
      <span className="truncate font-medium">{label}</span>
      {origin && (
        <span className="flex min-w-0 shrink items-center gap-1 rounded-full bg-background px-1.5 py-0.5 text-muted-foreground">
          <Folder className="size-3 shrink-0" aria-hidden />
          <span className="truncate">{origin}</span>
        </span>
      )}
      {onRemove && (
        <button
          type="button"
          aria-label={`Retirer ${label}`}
          className="shrink-0 rounded-full p-0.5 hover:bg-background"
          onClick={onRemove}
        >
          <X className="size-3" />
        </button>
      )}
    </li>
  )
}
