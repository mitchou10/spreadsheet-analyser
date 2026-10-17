export function AppHeader() {
  return (
    <header className="flex items-center gap-3 border-b bg-background px-4 py-2">
      <p className="fr-logo">
        République
        <br />
        Française
      </p>
      <div className="h-8 w-px bg-border" />
      <div>
        <p className="text-sm font-semibold">spreadsheet-analyser</p>
        <p className="hidden text-xs text-muted-foreground sm:block">
          Analysez vos fichiers tableurs avec un assistant conversationnel
        </p>
      </div>
    </header>
  )
}

