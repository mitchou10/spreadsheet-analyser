import { useState } from 'react'
import { listFiles } from '@/api/collections'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { CollectionSummary, SpreadsheetFile } from '@/types/collection'
import type { MessageScope } from '@/types/conversation'
import { FileSpreadsheet, Folder, Plus } from 'lucide-react'

interface ScopePickerProps {
  collections: CollectionSummary[]
  scope: MessageScope
  onChange: (scope: MessageScope) => void
  disabled?: boolean
}

type FilesState = SpreadsheetFile[] | 'loading' | 'error'

const has = (items: { id: string }[], id: string) => items.some((item) => item.id === id)

/** ChatGPT-style "+" menu: add whole collections, or only some files (grouped by their collection). */
export function ScopePicker({ collections, scope, onChange, disabled }: ScopePickerProps) {
  const [files, setFiles] = useState<Record<string, FilesState>>({})

  const loadFiles = (collectionId: string) => {
    if (files[collectionId] && files[collectionId] !== 'error') return
    setFiles((prev) => ({ ...prev, [collectionId]: 'loading' }))
    listFiles(collectionId).then(
      (list) => setFiles((prev) => ({ ...prev, [collectionId]: list })),
      () => setFiles((prev) => ({ ...prev, [collectionId]: 'error' })),
    )
  }

  const toggleCollection = ({ id, name }: CollectionSummary, checked: boolean) =>
    onChange({
      ...scope,
      collections: checked ? [...scope.collections, { id, name }] : scope.collections.filter((c) => c.id !== id),
    })

  const toggleFile = (file: SpreadsheetFile, collection: CollectionSummary, checked: boolean) =>
    onChange({
      ...scope,
      files: checked
        ? [...scope.files, { id: file.id, name: file.name, collection: { id: collection.id, name: collection.name } }]
        : scope.files.filter((f) => f.id !== file.id),
    })

  const countIn = (collectionId: string) => scope.files.filter((f) => f.collection.id === collectionId).length

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        disabled={disabled}
        aria-label="Ajouter des collections ou des fichiers"
        title="Ajouter des collections ou des fichiers"
        className="flex size-9 shrink-0 items-center justify-center rounded-full text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 disabled:opacity-50 data-[popup-open]:bg-muted"
      >
        <Plus className="size-5" />
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <Folder className="size-4" aria-hidden />
            Collections
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {collections.length === 0 && <DropdownMenuLabel>Aucune collection.</DropdownMenuLabel>}
            {collections.map((collection) => (
              <DropdownMenuCheckboxItem
                key={collection.id}
                closeOnClick={false}
                checked={has(scope.collections, collection.id)}
                onCheckedChange={(checked) => toggleCollection(collection, checked)}
              >
                <span className="truncate">{collection.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{collection.fileCount}</span>
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuSub>

        <DropdownMenuSub>
          <DropdownMenuSubTrigger>
            <FileSpreadsheet className="size-4" aria-hidden />
            Fichiers
          </DropdownMenuSubTrigger>
          <DropdownMenuSubContent>
            {collections.length === 0 && <DropdownMenuLabel>Aucune collection.</DropdownMenuLabel>}
            {collections.map((collection) => {
              const state = files[collection.id]
              const picked = countIn(collection.id)
              return (
                <DropdownMenuSub key={collection.id}>
                  <DropdownMenuSubTrigger onFocus={() => loadFiles(collection.id)} onMouseEnter={() => loadFiles(collection.id)}>
                    <Folder className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="truncate">{collection.name}</span>
                    {picked > 0 && (
                      <span className="shrink-0 rounded-full bg-primary px-1.5 text-xs text-primary-foreground">{picked}</span>
                    )}
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    <DropdownMenuLabel className="truncate">{collection.name}</DropdownMenuLabel>
                    {state === undefined || state === 'loading' ? (
                      <DropdownMenuLabel>Chargement…</DropdownMenuLabel>
                    ) : state === 'error' ? (
                      <DropdownMenuLabel className="text-destructive">Impossible de charger les fichiers.</DropdownMenuLabel>
                    ) : state.length === 0 ? (
                      <DropdownMenuLabel>Aucun fichier.</DropdownMenuLabel>
                    ) : (
                      state.map((file) => (
                        <DropdownMenuCheckboxItem
                          key={file.id}
                          closeOnClick={false}
                          checked={has(scope.files, file.id)}
                          onCheckedChange={(checked) => toggleFile(file, collection, checked)}
                        >
                          <span className="truncate">{file.name}</span>
                          {file.status !== 'ready' && (
                            <span className="shrink-0 text-xs text-muted-foreground">analyse {file.status}</span>
                          )}
                        </DropdownMenuCheckboxItem>
                      ))
                    )}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
              )
            })}
          </DropdownMenuSubContent>
        </DropdownMenuSub>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
