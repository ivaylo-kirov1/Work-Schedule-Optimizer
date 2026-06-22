export type UserRole = "MANAGER" | "EMPLOYEE"

export interface LoginResponse {
  access_token: string
  token_type: string
  role: string
}

export interface MeResponse {
  id: number
  email: string
  role: string
  employee_id: number | null
}

export interface EmployeeResponse {
  id: number
  name: string
  role: string
  hours_per_week: number
  deactivated_at: string | null
  is_active: boolean
}

export interface CredentialResponse {
  employee_id: number | null
  user_id: number
  email: string
  temp_password: string
}

export interface ManagerResponse {
  id: number
  email: string
  created_at: string
}

export interface ManagerCredentialResponse {
  user_id: number
  email: string
  temp_password: string
}

export interface PreferencesResponse {
  days: number[]
}

export interface ShiftTypeResponse {
  id: number
  name: string
  start_time: string
  end_time: string
  deactivated_at: string | null
  is_active: boolean
}

export type Regime = "SUMMARIZED" | "FIVE_DAY"

export interface SettingsResponse {
  off_weekdays: number[]
  regime: string
}

export interface NonWorkingDateResponse {
  id: number
  date: string
  note: string | null
}

export type LeaveRequestStatus = "PENDING" | "APPROVED" | "REJECTED"

export interface LeaveRequestResponse {
  id: number
  employee_id: number
  start_date: string
  end_date: string
  note: string | null
  status: LeaveRequestStatus
}

export type Algorithm = "GA" | "CP_SAT"

export interface GenerateRequestBody {
  algorithm: Algorithm
  start_month: string
  end_month: string
  monthly_norms: Record<string, number>
  staffing: Record<string, number>
}

export interface GenerateResponse {
  task_id: string
}

export type TaskStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED"

export interface TaskStatusResponse {
  task_id: string
  status: TaskStatus
  error: string | null
  created_at: string
  completed_at: string | null
}

export interface ScheduleListItem {
  id: number
  task_id: string | null
  start_date: string
  end_date: string
  algorithm: string
  fitness_score: number | null
  created_at: string
}

export interface SoftViolations {
  S1: number
  S2: number
  S3: number
  S4: number
  S5: number
  S6: number
}

export interface HardViolations {
  H1: number
  H2: number
  H3: number
  H4: number
  H5: number
  H6: number
  H7: number
  H8: number
  H9: number
}

export interface ScheduleEmployee {
  id: number
  name: string
  hours_per_week: number
}

export interface ScheduleShiftType {
  id: number
  name: string
  start_time: string
  end_time: string
}

export interface ScheduleAssignment {
  employee_id: number
  date: string
  shift_type_id: number | null
}

export interface ScheduleDetail {
  schedule_id: number
  algorithm: string
  start_date: string
  end_date: string
  fitness_score: number | null
  hard_violations: HardViolations
  soft_violations: SoftViolations
  employees: ScheduleEmployee[]
  shift_types: ScheduleShiftType[]
  assignments: ScheduleAssignment[]
}

export interface EmployeeScheduleEntry {
  date: string
  shift_type_id: number | null
  shift_type_name: string | null
  start_time: string | null
  end_time: string | null
}
