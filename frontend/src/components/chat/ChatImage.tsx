import { useEffect, useState } from 'react'
import { API_BASE_URL } from '@/lib/api'
import { ImageOff, Loader2 } from 'lucide-react'

// The images of an answer (its charts) are served by the backend, to the owner of the conversation: they need the
// session cookie, so they are fetched with it and shown from a blob. Blobs are kept for the page's lifetime, so an
// image is not fetched again when a message is re-rendered or scrolled back into view.
const blobs = new Map<string, Promise<string>>()

function loadBlob(url: string): Promise<string> {
  let blob = blobs.get(url)
  if (!blob) {
    blob = fetch(url, { credentials: 'include' }).then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return URL.createObjectURL(await response.blob())
    })
    blob.catch(() => blobs.delete(url)) // a failure is not remembered: the next render tries again
    blobs.set(url, blob)
  }
  return blob
}

interface ChatImageProps {
  src: string
  alt?: string
}

export function ChatImage({ src, alt }: ChatImageProps) {
  const [state, setState] = useState<{ src: string; url: string | null; failed: boolean }>({
    src,
    url: null,
    failed: false,
  })

  useEffect(() => {
    let cancelled = false
    loadBlob(`${API_BASE_URL}${src}`).then(
      (url) => !cancelled && setState({ src, url, failed: false }),
      () => !cancelled && setState({ src, url: null, failed: true }),
    )
    return () => {
      cancelled = true
    }
  }, [src])

  const current = state.src === src ? state : { src, url: null, failed: false }

  if (current.failed) {
    return (
      <span className="my-2 flex items-center gap-2 rounded-md border border-dashed p-3 text-xs text-muted-foreground">
        <ImageOff className="size-4 shrink-0" aria-hidden />
        {alt ? `${alt} (image indisponible)` : 'Image indisponible'}
      </span>
    )
  }
  if (!current.url) {
    return (
      <span
        className="my-2 flex aspect-[5/3] w-full items-center justify-center rounded-md bg-background/60 text-muted-foreground"
        role="img"
        aria-label={alt}
      >
        <Loader2 className="size-5 animate-spin" aria-hidden />
      </span>
    )
  }
  return (
    <a href={current.url} target="_blank" rel="noreferrer noopener" className="my-2 block" title="Ouvrir en grand">
      <img src={current.url} alt={alt ?? ''} className="w-full rounded-md border bg-white" loading="lazy" />
    </a>
  )
}
