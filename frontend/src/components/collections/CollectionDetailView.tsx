import { SidebarTrigger } from '@/components/ui/sidebar'
import type { CollectionSummary } from '@/types/collection'
import { FileList } from './FileList'
import { FileUploadButton } from './FileUploadButton'

interface CollectionDetailViewProps {
  collection: CollectionSummary | null
  onFilesSelected: (files: globalThis.FileList) => void
  onRetry: (fileId: string) => void
  onStop: (fileId: string) => void
  onDelete: (fileId: string) => void
}

export function CollectionDetailView({
  collection,
  onFilesSelected,
  onRetry,
  onStop,
  onDelete,
}: CollectionDetailViewProps) {
  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <span className="truncate text-sm font-medium">{collection?.name ?? 'Collection'}</span>
        </div>
        <FileUploadButton onFilesSelected={onFilesSelected} />
      </div>

      <div className="flex-1 overflow-auto p-4">
        <FileList files={collection?.files ?? []} onRetry={onRetry} onStop={onStop} onDelete={onDelete} />
      </div>
    </div>
  )
}
