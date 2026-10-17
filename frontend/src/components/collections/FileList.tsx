import { useState } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatBytes, formatDate } from '@/lib/format'
import type { SpreadsheetFile } from '@/types/collection'
import { FileDetailsDialog } from './FileDetailsDialog'
import { FileStatusBadge } from './FileStatusBadge'
import { FileSpreadsheet, RotateCw, Square, Trash2 } from 'lucide-react'

interface FileListProps {
  files: SpreadsheetFile[]
  onRetry: (fileId: string) => void
  onStop: (fileId: string) => void
  onDelete: (fileId: string) => void
}

export function FileList({ files, onRetry, onStop, onDelete }: FileListProps) {
  const [selectedFile, setSelectedFile] = useState<SpreadsheetFile | null>(null)
  const [fileToDelete, setFileToDelete] = useState<SpreadsheetFile | null>(null)

  if (files.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        <p>Aucun fichier dans cette collection. Importez votre premier fichier.</p>
      </div>
    )
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nom</TableHead>
            <TableHead>Taille</TableHead>
            <TableHead>Importé le</TableHead>
            <TableHead>Mis à jour le</TableHead>
            <TableHead>Statut</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {files.map((file) => (
            <TableRow key={file.id} className="cursor-pointer" onClick={() => setSelectedFile(file)}>
              <TableCell className="flex items-center gap-2 font-medium">
                <FileSpreadsheet className="size-4 text-muted-foreground" />
                {file.name}
              </TableCell>
              <TableCell className="text-muted-foreground">{formatBytes(file.sizeBytes)}</TableCell>
              <TableCell className="text-muted-foreground">{formatDate(file.uploadedAt)}</TableCell>
              <TableCell className="text-muted-foreground">{formatDate(file.updatedAt)}</TableCell>
              <TableCell>
                <FileStatusBadge status={file.status} />
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2" onClick={(event) => event.stopPropagation()}>
                  {file.status === 'processing' ? (
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={() => onStop(file.id)}>
                      <Square className="size-3.5" />
                      Stopper
                    </Button>
                  ) : (
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={() => onRetry(file.id)}>
                      <RotateCw className="size-3.5" />
                      Relancer
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="icon"
                    aria-label="Supprimer le fichier"
                    onClick={() => setFileToDelete(file)}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <FileDetailsDialog
        file={selectedFile}
        open={selectedFile !== null}
        onOpenChange={(open) => !open && setSelectedFile(null)}
      />

      <AlertDialog open={fileToDelete !== null} onOpenChange={(open) => !open && setFileToDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer « {fileToDelete?.name} » ?</AlertDialogTitle>
            <AlertDialogDescription>Cette action est irréversible.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (fileToDelete) onDelete(fileToDelete.id)
                setFileToDelete(null)
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
