import { LogOut, Menu } from "lucide-react"
import { useState } from "react"
import { NavLink, Outlet } from "react-router-dom"

import { MANAGER_NAV } from "@/layouts/nav-config"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useAuth } from "@/hooks/useAuth"
import { cn } from "@/lib/utils"

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-1 flex-col gap-1 px-3" aria-label="Manager navigation">
      {MANAGER_NAV.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
              )
            }
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            {item.label}
          </NavLink>
        )
      })}
    </nav>
  )
}

function SidebarFooter() {
  const { user, logout } = useAuth()
  return (
    <div className="px-3 pb-4">
      <Separator className="mb-3" />
      <p className="truncate px-3 text-xs text-muted-foreground" title={user?.email}>
        {user?.email}
      </p>
      <Button
        variant="ghost"
        className="mt-2 w-full justify-start"
        onClick={logout}
      >
        <LogOut className="h-4 w-4" aria-hidden />
        Log out
      </Button>
    </div>
  )
}

export function ManagerLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-64 shrink-0 flex-col border-r bg-sidebar py-4 md:flex">
        <div className="px-6 pb-4">
          <p className="text-sm font-semibold">Schedule Optimizer</p>
          <p className="text-xs text-muted-foreground">Manager workspace</p>
        </div>
        <NavList />
        <SidebarFooter />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b bg-background px-4 py-3 md:hidden">
          <Button
            variant="outline"
            size="icon"
            onClick={() => setMobileOpen((open) => !open)}
            aria-label="Toggle navigation"
            aria-expanded={mobileOpen}
          >
            <Menu className="h-4 w-4" />
          </Button>
          <span className="text-sm font-semibold">Schedule Optimizer</span>
        </header>

        {mobileOpen && (
          <div className="border-b bg-sidebar py-3 md:hidden">
            <NavList onNavigate={() => setMobileOpen(false)} />
            <SidebarFooter />
          </div>
        )}

        <main className="flex-1 overflow-x-hidden p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
