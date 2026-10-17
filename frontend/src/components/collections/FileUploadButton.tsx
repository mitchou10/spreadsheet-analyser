import { useRef } from 'react'
import { Button } from '@/components/ui/button'
import { Upload } from 'lucide-react'

interface FileUploadButtonProps {
  onFilesSelected: (files: FileList) => void
}

export function FileUploadButton({ onFilesSelected }: FileUploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".xlsx,.xls,.csv,.ods"
        className="hidden"
        onChange={(event) => {
          if (event.target.files && event.target.files.length > 0) {
            onFilesSelected(event.target.files)
          }
          event.target.value = ''
        }}
      />
      <Button size="sm" className="gap-2" onClick={() => inputRef.current?.click()}>
        <Upload className="size-4" />
        Importer des fichiers
      </Button>
    </>
  )
}
