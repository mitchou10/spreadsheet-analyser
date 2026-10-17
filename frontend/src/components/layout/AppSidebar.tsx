import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { useCurrentUser } from '@/auth/AuthContext'
import type { Conversation } from '@/types/conversation'
import { FileSpreadsheet, LogOut, SquarePen } from 'lucide-react'

interface AppSidebarProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  isCollectionsActive: boolean
  onShowCollections: () => void
}

export function AppSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  isCollectionsActive,
  onShowCollections,
}: AppSidebarProps) {
  const { user, logout } = useCurrentUser()

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
                    isActive={!isCollectionsActive && conversation.id === activeId}
                    onClick={() => onSelect(conversation.id)}
                  >
                    <span className="truncate">{conversation.title}</span>
                  </SidebarMenuButton>
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
    </Sidebar>
  )
}
