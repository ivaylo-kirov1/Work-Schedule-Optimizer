import {
  CalendarDays,
  CalendarOff,
  CalendarPlus,
  CalendarRange,
  KeyRound,
  Settings,
  ShieldCheck,
  Sliders,
  Users,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

export const MANAGER_NAV: NavItem[] = [
  { to: "/manager/schedule", label: "Schedule", icon: CalendarDays },
  { to: "/manager/generate", label: "Generate", icon: CalendarPlus },
  { to: "/manager/employees", label: "Employees", icon: Users },
  { to: "/manager/leave-requests", label: "Leave Requests", icon: CalendarRange },
  { to: "/manager/shift-types", label: "Shift Types", icon: Sliders },
  { to: "/manager/settings", label: "Company Settings", icon: Settings },
  {
    to: "/manager/non-working-dates",
    label: "Non-Working Dates",
    icon: CalendarOff,
  },
  { to: "/manager/managers", label: "Manager Accounts", icon: ShieldCheck },
  { to: "/manager/change-password", label: "Change Password", icon: KeyRound },
]

export const EMPLOYEE_NAV: NavItem[] = [
  { to: "/employee/schedule", label: "My Schedule", icon: CalendarDays },
  { to: "/employee/preferences", label: "My Preferences", icon: Sliders },
  {
    to: "/employee/leave-requests",
    label: "Leave Requests",
    icon: CalendarRange,
  },
  { to: "/employee/change-password", label: "Change Password", icon: KeyRound },
]
