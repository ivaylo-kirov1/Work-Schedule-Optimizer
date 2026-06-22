import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"

import { Spinner } from "@/components/ui/spinner"
import { useAuth } from "@/hooks/useAuth"
import type { UserRole } from "@/api/types"

interface ProtectedRouteProps {
  allowedRole: UserRole
  children: ReactNode
}

export function ProtectedRoute({ allowedRole, children }: ProtectedRouteProps) {
  const { user, isInitializing } = useAuth()
  const location = useLocation()

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading…" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (user.role !== allowedRole) {
    const home = user.role === "MANAGER" ? "/manager/schedule" : "/employee/schedule"
    return <Navigate to={home} replace />
  }

  return <>{children}</>
}
