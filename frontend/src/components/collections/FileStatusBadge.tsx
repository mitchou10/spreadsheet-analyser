import { Badge } from '@/components/ui/badge'
import type { FileAnalysisStatus } from '@/types/collection'

const STATUS_LABELS: Record<FileAnalysisStatus, string> = {
  pending: 'En attente',
  processing: 'Analyse en cours',
  ready: 'Analysé',
  error: 'Échec',
  stopped: 'Arrêtée',
}

const STATUS_VARIANTS: Record<FileAnalysisStatus, 'secondary' | 'outline' | 'default' | 'destructive'> = {
  pending: 'outline',
  processing: 'secondary',
  ready: 'default',
  error: 'destructive',
  stopped: 'outline',
}

export function FileStatusBadge({ status }: { status: FileAnalysisStatus }) {
  return <Badge variant={STATUS_VARIANTS[status]}>{STATUS_LABELS[status]}</Badge>
}
