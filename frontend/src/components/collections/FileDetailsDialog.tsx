import { useEffect, useState } from 'react'
import { getAnalysis } from '@/api/collections'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { formatBytes, formatDate } from '@/lib/format'
import type { AnalysisReport, SpreadsheetFile } from '@/types/collection'
import { FileStatusBadge } from './FileStatusBadge'

interface FileDetailsDialogProps {
  file: SpreadsheetFile | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

const NUMBER = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 })

function useAnalysis(file: SpreadsheetFile | null, open: boolean) {
  const [report, setReport] = useState<{ fileId: string; value: AnalysisReport } | null>(null)
  const [failure, setFailure] = useState<{ fileId: string; message: string } | null>(null)
  // `updatedAt` changes when the analysis finishes or is re-run, so the report follows the status.
  const fileId = file?.id
  const refreshKey = file ? `${file.status}-${file.updatedAt}` : null

  useEffect(() => {
    if (!open || !fileId) return
    let cancelled = false
    getAnalysis(fileId)
      .then((value) => !cancelled && setReport({ fileId, value }))
      .catch((e: unknown) => !cancelled && setFailure({ fileId, message: e instanceof Error ? e.message : 'Erreur' }))
    return () => {
      cancelled = true
    }
  }, [open, fileId, refreshKey])

  return {
    report: report && report.fileId === fileId ? report.value : null,
    failure: failure && failure.fileId === fileId ? failure.message : null,
  }
}

export function FileDetailsDialog({ file, open, onOpenChange }: FileDetailsDialogProps) {
  const { report, failure } = useAnalysis(file, open)

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
              {failure && <p className="text-sm text-destructive">{failure}</p>}
              {report?.error && <p className="text-sm text-destructive">{report.error}</p>}
              {!report?.sheets.length && !report?.error && !failure && (
                <p className="text-sm text-muted-foreground">
                  {file.status === 'ready' ? 'Chargement…' : "Le détail apparaîtra une fois l'analyse terminée."}
                </p>
              )}
              {report?.sheets.map((sheet) => (
                <div key={sheet.name} className="flex flex-col gap-1.5">
                  <p className="text-sm">
                    <span className="font-medium">{sheet.name}</span>
                    <span className="text-muted-foreground">
                      {' '}
                      · {NUMBER.format(sheet.rows)} ligne{sheet.rows > 1 ? 's' : ''} · {sheet.columns.length} colonne
                      {sheet.columns.length > 1 ? 's' : ''}
                    </span>
                  </p>
                  {sheet.warnings.map((warning) => (
                    <p key={warning} className="text-xs text-muted-foreground">
                      ⚠ {warning}
                    </p>
                  ))}
                  <div className="max-h-64 overflow-auto rounded-md border">
                    <table className="w-full text-xs">
                      <thead className="sticky top-0 bg-muted text-left">
                        <tr>
                          <th className="px-2 py-1.5">Colonne</th>
                          <th className="px-2 py-1.5">Type</th>
                          <th className="px-2 py-1.5 text-right">Vides</th>
                          <th className="px-2 py-1.5 text-right">Distincts</th>
                          <th className="px-2 py-1.5 text-right">Min – Max</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sheet.columns.map((column) => (
                          <tr key={column.name} className="border-t">
                            <td className="px-2 py-1.5 font-medium">{column.name}</td>
                            <td className="px-2 py-1.5 text-muted-foreground">{column.type}</td>
                            <td className="px-2 py-1.5 text-right">{NUMBER.format(column.nulls)}</td>
                            <td className="px-2 py-1.5 text-right">
                              {column.distinctExact ? '' : '≥ '}
                              {NUMBER.format(column.distinct)}
                            </td>
                            <td className="px-2 py-1.5 text-right text-muted-foreground">
                              {column.numeric && column.numeric.min !== null && column.numeric.max !== null
                                ? `${NUMBER.format(column.numeric.min)} – ${NUMBER.format(column.numeric.max)}`
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
