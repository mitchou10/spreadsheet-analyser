import { useEffect, useState, type DragEvent, type KeyboardEvent } from 'react'
import { listFiles } from '@/api/collections'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { ModelOption } from '@/types/model'
import { ModelSelector } from './ModelSelector'
import { ScopePicker } from './ScopePicker'
import { ScopeChip } from './ScopeChip'
import { UploadDialog, type UploadedFile } from './UploadDialog'
import type { CollectionSummary } from '@/types/collection'
import { emptyScope, type MessageScope } from '@/types/conversation'
import { ArrowUp, Square } from 'lucide-react'

interface ChatInputProps {
  models: ModelOption[]
  modelsLoading: boolean
  modelsError: string | null
  selectedModel: string | null
  onModelChange: (modelId: string) => void
  isAnswering: boolean
  collections: CollectionSummary[]
  onSend: (content: string, scope: MessageScope) => void
  onCancel: () => void
  // A file was imported (or a collection created): the collections' file counts changed.
  onCollectionsChanged: () => void
}

export function ChatInput({ models, modelsLoading, modelsError, selectedModel, onModelChange, isAnswering, collections, onSend, onCancel, onCollectionsChanged }: ChatInputProps) {
  const [value, setValue] = useState('')
  // The scope belongs to the next message only: it is cleared once sent.
  const [scope, setScope] = useState<MessageScope>(emptyScope)

  const [importOpen, setImportOpen] = useState(false)
  // Files dropped on the composer, handed to the import dialog.
  const [dropped, setDropped] = useState<File[]>([])

  // A file imported just now is analysed asynchronously, and the agent can only query an analysed file: the
  // composer follows the analysis and holds the send until it is done.
  const analysing = scope.files.filter((file) => file.status === 'pending' || file.status === 'processing')
  const analysingKey = analysing.map((file) => file.id).join(',')
  useEffect(() => {
    if (!analysingKey) return
    const collectionIds = [...new Set(scope.files.filter((f) => analysingKey.split(',').includes(f.id)).map((f) => f.collection.id))]
    const timer = setInterval(async () => {
      try {
        const fresh = (await Promise.all(collectionIds.map((id) => listFiles(id)))).flat()
        setScope((current) => ({
          ...current,
          files: current.files.map((file) => {
            const latest = fresh.find((candidate) => candidate.id === file.id)
            return latest && file.status ? { ...file, status: latest.status } : file
          }),
        }))
      } catch {
        // a missed poll is harmless: the next one catches up
      }
    }, 2000)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysingKey])

  const addUploaded = (uploaded: UploadedFile[]) =>
    setScope((current) => ({
      ...current,
      files: [
        ...current.files,
        ...uploaded
          .filter(({ file }) => !current.files.some((existing) => existing.id === file.id))
          .map(({ file, collection }) => ({ id: file.id, name: file.name, collection, status: file.status })),
      ],
    }))

  const openImport = (files: File[] = []) => {
    setDropped(files)
    setImportOpen(true)
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    if (isAnswering || event.dataTransfer.files.length === 0) return
    openImport(Array.from(event.dataTransfer.files))
  }

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || isAnswering || analysing.length > 0) return
    onSend(trimmed, scope)
    setValue('')
    setScope(emptyScope)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const hasScope = scope.collections.length > 0 || scope.files.length > 0

  return (
    <div className="bg-background px-4 pt-2 pb-4">
      <div
        className="mx-auto max-w-3xl rounded-3xl border bg-card px-3 pt-2.5 pb-2 shadow-sm focus-within:ring-2 focus-within:ring-ring/30"
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
      >
        {hasScope && (
          <ul className="mb-2 flex flex-wrap gap-1.5 px-1" aria-label="Périmètre de la question">
            {scope.collections.map((c) => (
              <ScopeChip
                key={c.id}
                kind="collection"
                label={c.name}
                onRemove={() => setScope({ ...scope, collections: scope.collections.filter((x) => x.id !== c.id) })}
              />
            ))}
            {scope.files.map((f) => (
              <ScopeChip
                key={f.id}
                kind="file"
                label={f.name}
                origin={f.collection.name}
                status={f.status}
                onRemove={() => setScope({ ...scope, files: scope.files.filter((x) => x.id !== f.id) })}
              />
            ))}
          </ul>
        )}
        {analysing.length > 0 && (
          <p className="mb-1 px-1 text-xs text-muted-foreground" role="status">
            Analyse en cours : l'envoi sera possible dès que le fichier est prêt.
          </p>
        )}
        <Textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Posez une question sur vos fichiers…"
          rows={1}
          className="max-h-40 min-h-10 resize-none border-0 bg-transparent px-1 py-1.5 shadow-none focus-visible:border-0 focus-visible:ring-0 dark:bg-transparent"
        />
        <div className="mt-1 flex items-center gap-1">
          <ScopePicker
            collections={collections}
            scope={scope}
            onChange={setScope}
            onImport={() => openImport()}
            disabled={isAnswering}
          />
          <ModelSelector
            models={models}
            isLoading={modelsLoading}
            error={modelsError}
            value={selectedModel}
            onChange={onModelChange}
          />
          <div className="ml-auto">
            {isAnswering ? (
              <Button size="icon" variant="outline" className="rounded-full" aria-label="Arrêter la réponse" onClick={onCancel}>
                <Square className="size-4" />
              </Button>
            ) : (
              <Button
                size="icon"
                className="rounded-full"
                aria-label="Envoyer"
                title={analysing.length > 0 ? "Analyse du fichier en cours…" : undefined}
                onClick={submit}
                disabled={!value.trim() || analysing.length > 0}
              >
                <ArrowUp className="size-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
      <UploadDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        collections={collections}
        initialFiles={dropped}
        onUploaded={addUploaded}
        onCollectionsChanged={onCollectionsChanged}
      />
    </div>
  )
}
