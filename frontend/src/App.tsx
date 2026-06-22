import {
  Component,
  lazy,
  Suspense,
  type ErrorInfo,
  type ReactNode,
} from "react"
import { Navigate, Route, Routes } from "react-router-dom"

import { ProtectedRoute } from "@/components/ProtectedRoute"
import { Spinner } from "@/components/ui/spinner"
import { useAuth } from "@/hooks/useAuth"
import { EmployeeLayout } from "@/layouts/EmployeeLayout"
import { ManagerLayout } from "@/layouts/ManagerLayout"
import { LoginPage } from "@/pages/LoginPage"

const ChangePasswordPage = lazy(() =>
  import("@/pages/ChangePasswordPage").then((m) => ({
    default: m.ChangePasswordPage,
  }))
)
const MyLeaveRequestsPage = lazy(() =>
  import("@/pages/employee/MyLeaveRequestsPage").then((m) => ({
    default: m.MyLeaveRequestsPage,
  }))
)
const MySchedulePage = lazy(() =>
  import("@/pages/employee/MySchedulePage").then((m) => ({
    default: m.MySchedulePage,
  }))
)
const PreferencesPage = lazy(() =>
  import("@/pages/employee/PreferencesPage").then((m) => ({
    default: m.PreferencesPage,
  }))
)
const EmployeesPage = lazy(() =>
  import("@/pages/manager/EmployeesPage").then((m) => ({
    default: m.EmployeesPage,
  }))
)
const GeneratePage = lazy(() =>
  import("@/pages/manager/GeneratePage").then((m) => ({
    default: m.GeneratePage,
  }))
)
const LeaveRequestsPage = lazy(() =>
  import("@/pages/manager/LeaveRequestsPage").then((m) => ({
    default: m.LeaveRequestsPage,
  }))
)
const ManagerAccountsPage = lazy(() =>
  import("@/pages/manager/ManagerAccountsPage").then((m) => ({
    default: m.ManagerAccountsPage,
  }))
)
const NonWorkingDatesPage = lazy(() =>
  import("@/pages/manager/NonWorkingDatesPage").then((m) => ({
    default: m.NonWorkingDatesPage,
  }))
)
const SchedulePage = lazy(() =>
  import("@/pages/manager/SchedulePage").then((m) => ({
    default: m.SchedulePage,
  }))
)
const SettingsPage = lazy(() =>
  import("@/pages/manager/SettingsPage").then((m) => ({
    default: m.SettingsPage,
  }))
)
const ShiftTypesPage = lazy(() =>
  import("@/pages/manager/ShiftTypesPage").then((m) => ({
    default: m.ShiftTypesPage,
  }))
)

function PageFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Spinner label="Loading…" />
    </div>
  )
}

class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen items-center justify-center">
          <p className="text-muted-foreground">
            Something went wrong.{" "}
            <a href="/" className="underline">
              Go home
            </a>
          </p>
        </div>
      )
    }
    return this.props.children
  }
}

function RootRedirect() {
  const { user, isInitializing } = useAuth()

  if (isInitializing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner label="Loading…" />
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />
  return (
    <Navigate
      to={user.role === "MANAGER" ? "/manager/schedule" : "/employee/schedule"}
      replace
    />
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageFallback />}>
        <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          path="/manager"
          element={
            <ProtectedRoute allowedRole="MANAGER">
              <ManagerLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="schedule" replace />} />
          <Route path="schedule" element={<SchedulePage />} />
          <Route path="generate" element={<GeneratePage />} />
          <Route path="employees" element={<EmployeesPage />} />
          <Route path="leave-requests" element={<LeaveRequestsPage />} />
          <Route path="shift-types" element={<ShiftTypesPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="non-working-dates" element={<NonWorkingDatesPage />} />
          <Route path="managers" element={<ManagerAccountsPage />} />
          <Route path="change-password" element={<ChangePasswordPage />} />
        </Route>

        <Route
          path="/employee"
          element={
            <ProtectedRoute allowedRole="EMPLOYEE">
              <EmployeeLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="schedule" replace />} />
          <Route path="schedule" element={<MySchedulePage />} />
          <Route path="preferences" element={<PreferencesPage />} />
          <Route path="leave-requests" element={<MyLeaveRequestsPage />} />
          <Route path="change-password" element={<ChangePasswordPage />} />
        </Route>

        <Route path="/" element={<RootRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
