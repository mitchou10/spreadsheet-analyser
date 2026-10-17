import { useEffect, useRef, useState } from 'react'
import { createCollection, uploadFiles } from '@/api/collections'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import type { CollectionSummary, SpreadsheetFile } from '@/types/collection'
import { FileSpreadsheet, Loader2, X } from 'lucide-react'

const ACCEPT = '.csv,.xlsx,.xlsm,.xls,.ods'
const NEW_COLLECTION = '__new__'
const LAST_COLLECTION_KEY = 'chat-upload-collection'

const remembered = (): string | null => {
  try {
    return localStorage.getItem(LAST_COLLECTION_KEY)
  } catch {
    return null
  }
}

const remember = (id: string) => {
  try {
    localStorage.setItem(LAST_COLLECTION_KEY, id)
  } catch {
    // private window or blocked storage: the choice is only a convenience
  }
}

export interface UploadedFile {
  file: SpreadsheetFile
  collection: { id: string; name: string }
}

interface UploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  // Only the collections the person owns can receive files (a shared one is read-only).
  collections: CollectionSummary[]
  // Files already chosen, e.g. dropped on the composer.
  initialFiles: File[]
  onUploaded: (uploaded: UploadedFile[]) => void
  onCollectionsChanged: () => void
}

/** Import files from the chat into one of my collections (or a new one), then attach them to the question. */
export function UploadDialog({ open, onOpenChange, collections, initialFiles, onUploaded, onCollectionsChanged }: UploadDialogProps) {
  const owned = collections.filter((collection) => collection.isOwner)
  const [files, setFiles] = useState<File[]>([])
  const [target, setTarget] = useState<string>(NEW_COLLECTION)
  const [newName, setNewName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const picker = useRef<HTMLInputElement>(null)

  // Each time the dialog opens: start from what was dropped, and from the collection used last time.
  useEffect(() => {
    if (!open) return
    setFiles(initialFiles)
    setError(null)
    const last = remembered()
    setTarget(owned.some((c) => c.id === last) ? (last as string) : (owned[0]?.id ?? NEW_COLLECTION))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const addFiles = (selected: FileList | null) => {
    if (!selected) return
    setFiles((current) => [...current, ...Array.from(selected).filter((file) => !current.some((c) => c.name === file.name))])
    if (picker.current) picker.current.value = ''
  }

  const creating = target === NEW_COLLECTION
  const canSubmit = files.length > 0 && (!creating || newName.trim().length > 0) && !busy

  const submit = async () => {
    setBusy(true)
    setError(null)
    try {
      const collection = creating
        ? await createCollection(newName.trim())
        : (owned.find((c) => c.id === target) as CollectionSummary)
      const uploaded = await uploadFiles(collection.id, files)
      remember(collection.id)
      onCollectionsChanged()
      onUploaded(uploaded.map((file) => ({ file, collection: { id: collection.id, name: collection.name } })))
      onOpenChange(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : "L'import a échoué")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Importer un fichier</DialogTitle>
          <DialogDescription>
            Le fichier est ajouté à une collection, analysé, puis joint à votre question. Formats : csv, xlsx, xls, ods.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">Fichiers</span>
            {files.length > 0 && (
              <ul className="flex flex-col gap-1">
                {files.map((file) => (
                  <li key={file.name} className="flex items-center gap-2 rounded-lg bg-muted px-2.5 py-1.5 text-xs">
                    <FileSpreadsheet className="size-3.5 shrink-0" aria-hidden />
                    <span className="truncate">{file.name}</span>
                    <button
                      type="button"
                      aria-label={`Retirer ${file.name}`}
                      className="ml-auto rounded-full p-0.5 hover:bg-background"
                      onClick={() => setFiles((current) => current.filter((c) => c !== file))}
                      disabled={busy}
                    >
                      <X className="size-3" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <input
              ref={picker}
              type="file"
              multiple
              accept={ACCEPT}
              className="sr-only"
              aria-label="Choisir des fichiers"
              onChange={(event) => addFiles(event.target.files)}
            />
            <Button type="button" variant="outline" size="sm" className="w-fit" onClick={() => picker.current?.click()} disabled={busy}>
              {files.length > 0 ? 'Ajouter un autre fichier' : 'Choisir des fichiers'}
            </Button>
          </div>

          <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
            Collection
            <select
              value={target}
              onChange={(event) => setTarget(event.target.value)}
              disabled={busy}
              className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm font-normal text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {owned.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))}
              <option value={NEW_COLLECTION}>Nouvelle collection…</option>
            </select>
          </label>

          {creating && (
            <Input
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="Nom de la nouvelle collection"
              aria-label="Nom de la nouvelle collection"
              disabled={busy}
            />
          )}

          {error && (
            <p role="alert" className="text-xs text-destructive">
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
            Annuler
          </Button>
          <Button type="button" onClick={submit} disabled={!canSubmit}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden />}
            Importer
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
