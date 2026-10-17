import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SidebarTrigger } from '@/components/ui/sidebar'
import type { CollectionSummary } from '@/types/collection'
import { FileSpreadsheet } from 'lucide-react'

interface CollectionsListViewProps {
  collections: CollectionSummary[]
  onSelect: (id: string) => void
}

export function CollectionsListView({ collections, onSelect }: CollectionsListViewProps) {
  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <SidebarTrigger />
        <span className="truncate text-sm font-medium">Collections</span>
      </div>

      <div className="grid flex-1 auto-rows-min grid-cols-1 gap-4 overflow-auto p-6 sm:grid-cols-2 lg:grid-cols-3">
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
              {collection.files.length} fichier{collection.files.length > 1 ? 's' : ''}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

