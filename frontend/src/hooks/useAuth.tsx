import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import { apiClient, TOKEN_STORAGE_KEY } from "@/api/client"
import type { LoginResponse, MeResponse, UserRole } from "@/api/types"

interface AuthUser {
  id: number
  email: string
  role: UserRole
  employeeId: number | null
}

interface AuthContextValue {
  user: AuthUser | null
  isInitializing: boolean
  login: (email: string, password: string) => Promise<UserRole>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function normalizeRole(role: string): UserRole {
  return role === "MANAGER" ? "MANAGER" : "EMPLOYEE"
}

async function fetchCurrentUser(): Promise<AuthUser> {
  const { data } = await apiClient.get<MeResponse>("/api/auth/me")
  return {
    id: data.id,
    email: data.email,
    role: normalizeRole(data.role),
    employeeId: data.employee_id,
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  // only block the UI on startup if there is a token to validate
  const [isInitializing, setIsInitializing] = useState(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) !== null
  )

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY)
    if (!token) return

    let active = true
    fetchCurrentUser()
      .then((loadedUser) => {
        if (active) setUser(loadedUser)
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_STORAGE_KEY)
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setIsInitializing(false)
      })

    return () => {
      active = false
    }
  }, [])

  const login = useCallback(
    async (email: string, password: string): Promise<UserRole> => {
      const { data } = await apiClient.post<LoginResponse>("/api/auth/login", {
        email,
        password,
      })
      localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
      const loadedUser = await fetchCurrentUser()
      setUser(loadedUser)
      return loadedUser.role
    },
    []
  )

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    setUser(null)
    window.location.assign("/login")
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, isInitializing, login, logout }),
    [user, isInitializing, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
