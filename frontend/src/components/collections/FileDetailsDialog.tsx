import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { formatBytes, formatDate } from '@/lib/format'
import type { SpreadsheetFile } from '@/types/collection'
import { FileStatusBadge } from './FileStatusBadge'

interface FileDetailsDialogProps {
  file: SpreadsheetFile | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function FileDetailsDialog({ file, open, onOpenChange }: FileDetailsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="truncate">{file?.name}</DialogTitle>
        </DialogHeader>

        {file && (
          <div className="flex flex-col gap-6">
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-medium">Métadonnées</h3>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
                <dt className="text-muted-foreground">Taille</dt>
                <dd>{formatBytes(file.sizeBytes)}</dd>
                <dt className="text-muted-foreground">Importé le</dt>
                <dd>{formatDate(file.uploadedAt)}</dd>
                <dt className="text-muted-foreground">Mis à jour le</dt>
                <dd>{formatDate(file.updatedAt)}</dd>
                <dt className="text-muted-foreground">Statut</dt>
                <dd>
                  <FileStatusBadge status={file.status} />
                </dd>
              </dl>
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-medium">Analyse</h3>
              <p className="text-sm text-muted-foreground">Le détail de l'analyse sera disponible prochainement.</p>
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
