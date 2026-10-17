import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SidebarTrigger } from '@/components/ui/sidebar'
import type { CollectionSummary } from '@/types/collection'
import { FileSpreadsheet, Plus } from 'lucide-react'
import { CreateCollectionDialog } from './CreateCollectionDialog'

interface CollectionsListViewProps {
  collections: CollectionSummary[]
  isLoading: boolean
  onSelect: (id: string) => void
  onCreate: (name: string, description?: string) => Promise<unknown>
}

export function CollectionsListView({ collections, isLoading, onSelect, onCreate }: CollectionsListViewProps) {
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <span className="truncate text-sm font-medium">Collections</span>
        </div>
        <Button size="sm" className="gap-2" onClick={() => setIsCreateOpen(true)}>
          <Plus className="size-4" />
          Nouvelle collection
        </Button>
      </div>

      <div className="grid flex-1 auto-rows-min grid-cols-1 gap-4 overflow-auto p-6 sm:grid-cols-2 lg:grid-cols-3">
        {!isLoading && collections.length === 0 && (
          <p className="col-span-full py-12 text-center text-muted-foreground">
            Aucune collection. Créez la première pour y importer vos fichiers.
          </p>
        )}
        {collections.map((collection) => (
          <Card
            key={collection.id}
            className="cursor-pointer transition-colors hover:bg-accent"
            onClick={() => onSelect(collection.id)}
          >
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <FileSpreadsheet className="size-4 text-muted-foreground" />
                {collection.name}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {collection.fileCount} fichier{collection.fileCount > 1 ? 's' : ''}{!collection.isOwner && ' · partagée avec vous'}
            </CardContent>
          </Card>
        ))}
      </div>

      <CreateCollectionDialog open={isCreateOpen} onOpenChange={setIsCreateOpen} onCreate={onCreate} />
    </div>
  )
}
