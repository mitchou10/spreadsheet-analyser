import { useState, type FormEvent } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { useAdminAccess } from '@/hooks/useAdminAccess'
import type { AdminCollection, Person } from '@/types/admin'
import { Crown, Eye, FileSpreadsheet, Plus, Shield, X } from 'lucide-react'

type Mode = 'collections' | 'people'

function GrantForm({ onGrant }: { onGrant: (email: string) => Promise<boolean> }) {
  const [email, setEmail] = useState('')
  const [pending, setPending] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setPending(true)
    if (await onGrant(email.trim())) setEmail('')
    setPending(false)
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <Input
        type="email"
        required
        placeholder="email@exemple.fr"
        aria-label="Email à qui donner l'accès"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Button type="submit" size="sm" className="gap-1.5" disabled={pending || email.trim() === ''}>
        <Plus className="size-4" />
        Donner l'accès
      </Button>
    </form>
  )
}

function CollectionCard({
  collection,
  onGrant,
  onRevoke,
}: {
  collection: AdminCollection
  onGrant: (collectionId: string, email: string) => Promise<boolean>
  onRevoke: (collectionId: string, email: string) => Promise<boolean>
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <FileSpreadsheet className="size-4 text-muted-foreground" />
          {collection.name}
          <span className="text-xs font-normal text-muted-foreground">
            {collection.fileCount} fichier{collection.fileCount > 1 ? 's' : ''}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <p className="flex items-center gap-2">
          <Crown className="size-4 text-muted-foreground" aria-hidden />
          <span className="text-muted-foreground">Propriétaire</span>
          <span className="font-medium">{collection.ownerEmail ?? `utilisateur ${collection.ownerId}`}</span>
        </p>

        <div className="flex flex-col gap-1.5">
          <p className="flex items-center gap-2 text-muted-foreground">
            <Eye className="size-4" aria-hidden />
            Accès en lecture
          </p>
          {collection.sharedWith.length === 0 ? (
            <p className="text-muted-foreground">Personne d'autre.</p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {collection.sharedWith.map((access) => (
                <li key={access.email}>
                  <Badge variant="secondary" className="gap-1.5 py-3 pr-1">
                    {access.email}
                    <button
                      type="button"
                      aria-label={`Retirer l'accès de ${access.email}`}
                      className="rounded p-0.5 hover:bg-background"
                      onClick={() => onRevoke(collection.id, access.email)}
                    >
                      <X className="size-3.5" />
                    </button>
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </div>

        <GrantForm onGrant={(email) => onGrant(collection.id, email)} />
      </CardContent>
    </Card>
  )
}

function PeopleTable({
  people,
  onRevoke,
}: {
  people: Person[]
  onRevoke: (collectionId: string, email: string) => Promise<boolean>
}) {
  return (
    <div className="overflow-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="bg-muted text-left">
          <tr>
            <th className="px-3 py-2">Personne</th>
            <th className="px-3 py-2">Collections</th>
          </tr>
        </thead>
        <tbody>
          {people.map((person) => (
            <tr key={person.email ?? person.userId} className="border-t align-top">
              <td className="px-3 py-2 font-medium">{person.email ?? `utilisateur ${person.userId}`}</td>
              <td className="px-3 py-2">
                <ul className="flex flex-wrap gap-2">
                  {person.collections.map((collection) => (
                    <li key={collection.collectionId}>
                      <Badge variant={collection.role === 'owner' ? 'default' : 'outline'} className="gap-1.5 py-3">
                        {collection.name}
                        <span className="opacity-70">{collection.role === 'owner' ? 'propriétaire' : 'lecture'}</span>
                        {collection.role === 'viewer' && person.email && (
                          <button
                            type="button"
                            aria-label={`Retirer l'accès de ${person.email} à ${collection.name}`}
                            className="rounded p-0.5 hover:bg-muted"
                            onClick={() => onRevoke(collection.collectionId, person.email!)}
                          >
                            <X className="size-3.5" />
                          </button>
                        )}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function AdminView() {
  const admin = useAdminAccess()
  const [mode, setMode] = useState<Mode>('collections')

  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <Shield className="size-4 text-muted-foreground" aria-hidden />
          <span className="text-sm font-medium">Administration · accès</span>
        </div>
        <div className="flex gap-1" role="group" aria-label="Affichage">
          <Button size="sm" variant={mode === 'collections' ? 'default' : 'outline'} onClick={() => setMode('collections')}>
            Par collection
          </Button>
          <Button size="sm" variant={mode === 'people' ? 'default' : 'outline'} onClick={() => setMode('people')}>
            Par personne
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {admin.error && (
          <p role="alert" className="mb-4 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {admin.error}
          </p>
        )}
        {!admin.isLoading && admin.collections.length === 0 && !admin.error && (
          <p className="py-12 text-center text-muted-foreground">Aucune collection pour le moment.</p>
        )}
        {mode === 'collections' ? (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {admin.collections.map((collection) => (
              <CollectionCard key={collection.id} collection={collection} onGrant={admin.grant} onRevoke={admin.revoke} />
            ))}
          </div>
        ) : (
          <PeopleTable people={admin.people} onRevoke={admin.revoke} />
        )}
      </div>
    </div>
  )
}
