import { useEffect, useState } from 'react'
import { Markdown } from '@/components/chat/Markdown'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { API_BASE_URL } from '@/lib/api'

type Tab = 'changelog' | 'mcp'

const TABS: { id: Tab; label: string }[] = [
  { id: 'changelog', label: 'Nouveautés' },
  { id: 'mcp', label: 'Connecter un agent (MCP)' },
]

interface AboutDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  frontendVersion: string
  backendVersion: string | null
}

/** The version of the app, what changed in each release, and how to connect an agent over MCP. */
export function AboutDialog({ open, onOpenChange, frontendVersion, backendVersion }: AboutDialogProps) {
  const [tab, setTab] = useState<Tab>('changelog')
  const [changelog, setChangelog] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const [mcpGuide, setMcpGuide] = useState<string | null>(null)
  const [mcpFailed, setMcpFailed] = useState(false)

  // The changelog is a separate chunk, fetched the first time the dialog is opened.
  useEffect(() => {
    if (!open || changelog !== null) return
    import('../../../CHANGELOG.md?raw').then(
      (module) => setChangelog(module.default.replace(/^# .*\n+/, '')),
      () => setFailed(true),
    )
  }, [open, changelog])

  // The guide is a markdown file of the backend (with the real address of the server), read when its tab is opened.
  useEffect(() => {
    if (!open || tab !== 'mcp' || mcpGuide !== null) return
    fetch(`${API_BASE_URL}/api/help/mcp`, { credentials: 'include' }).then(
      async (response) => (response.ok ? setMcpGuide(await response.text()) : setMcpFailed(true)),
      () => setMcpFailed(true),
    )
  }, [open, tab, mcpGuide])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] flex-col gap-3 sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>spreadsheet-analyser v{frontendVersion}</DialogTitle>
          <DialogDescription>
            Interface v{frontendVersion}
            {backendVersion ? ` · serveur v${backendVersion}` : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-1 border-b pb-2" role="tablist" aria-label="Informations">
          {TABS.map((item) => (
            <Button
              key={item.id}
              type="button"
              role="tab"
              size="sm"
              variant={tab === item.id ? 'secondary' : 'ghost'}
              aria-selected={tab === item.id}
              onClick={() => setTab(item.id)}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto pr-1 text-sm" role="tabpanel">
          {tab === 'changelog' &&
            (changelog !== null ? (
              <Markdown>{changelog}</Markdown>
            ) : failed ? (
              <p className="text-destructive">Le journal des modifications n'a pas pu être chargé.</p>
            ) : (
              <p className="text-muted-foreground">Chargement…</p>
            ))}
          {tab === 'mcp' &&
            (mcpGuide !== null ? (
              <Markdown>{mcpGuide}</Markdown>
            ) : mcpFailed ? (
              <p className="text-destructive">Le guide n'a pas pu être chargé.</p>
            ) : (
              <p className="text-muted-foreground">Chargement…</p>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
