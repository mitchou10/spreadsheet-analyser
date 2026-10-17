import { Button } from '@/components/ui/button'
import { useCurrentUser } from './auth/AuthContext'
import { AppHeader } from './components/layout/AppHeader'
import { AppShell } from './components/layout/AppShell'

function App() {
  const { isAuthenticated, isLoading, login } = useCurrentUser()

  if (isLoading) return null

  if (!isAuthenticated) {
    return (
      <div className="flex h-full flex-1 flex-col">
        <AppHeader />
        <section className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
          <div>
            <h1 className="text-2xl font-semibold">spreadsheet-analyser</h1>
            <p className="text-muted-foreground">Connectez-vous pour analyser vos fichiers tableurs.</p>
          </div>
          <Button onClick={() => login()}>Se connecter</Button>
        </section>
      </div>
    )
  }

  return <AppShell />
}

export default App
