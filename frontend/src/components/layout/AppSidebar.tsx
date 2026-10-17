import { useState } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { useCurrentUser } from '@/auth/AuthContext'
import type { Conversation } from '@/types/conversation'
import { FileSpreadsheet, LogOut, Shield, SquarePen, Trash2 } from 'lucide-react'

interface AppSidebarProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  onDelete: (id: string) => void
  isCollectionsActive: boolean
  onShowCollections: () => void
  isAdminActive: boolean
  onShowAdmin: () => void
}

export function AppSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  isCollectionsActive,
  onShowCollections,
  isAdminActive,
  onShowAdmin,
}: AppSidebarProps) {
  const { user, logout } = useCurrentUser()
  const [conversationToDelete, setConversationToDelete] = useState<Conversation | null>(null)

  return (
    <Sidebar collapsible="icon" className="h-full">
      <SidebarHeader>
        <div className="flex items-center gap-2">
          <SidebarTrigger />
          <Button variant="outline" className="flex-1 justify-start gap-2" onClick={onNewChat}>
            <SquarePen className="size-4" />
            Nouvelle conversation
          </Button>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton isActive={isCollectionsActive} onClick={onShowCollections}>
                  <FileSpreadsheet className="size-4" />
                  Collections
                </SidebarMenuButton>
              </SidebarMenuItem>
              {user?.isAdmin && (
                <SidebarMenuItem>
                  <SidebarMenuButton isActive={isAdminActive} onClick={onShowAdmin}>
                    <Shield className="size-4" />
                    Administration
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {conversations.map((conversation) => (
                <SidebarMenuItem key={conversation.id}>
                  <SidebarMenuButton
                    isActive={!isCollectionsActive && !isAdminActive && conversation.id === activeId}
                    onClick={() => onSelect(conversation.id)}
                  >
                    <span className="truncate">{conversation.title}</span>
                  </SidebarMenuButton>
                  <SidebarMenuAction
                    showOnHover
                    aria-label="Supprimer la conversation"
                    onClick={() => setConversationToDelete(conversation)}
                  >
                    <Trash2 />
                  </SidebarMenuAction>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        {user && (
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => logout()}>
                <LogOut className="size-4" />
                <span className="truncate">{user.name}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        )}
      </SidebarFooter>

      <AlertDialog
        open={conversationToDelete !== null}
        onOpenChange={(open) => !open && setConversationToDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer « {conversationToDelete?.title} » ?</AlertDialogTitle>
            <AlertDialogDescription>La conversation et ses messages seront supprimés définitivement.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (conversationToDelete) onDelete(conversationToDelete.id)
                setConversationToDelete(null)
              }}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Sidebar>
  )
}
