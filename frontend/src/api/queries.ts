import { useQuery } from "@tanstack/react-query"

import { apiClient } from "@/api/client"
import type {
  EmployeeResponse,
  ManagerResponse,
  NonWorkingDateResponse,
  SettingsResponse,
  ShiftTypeResponse,
} from "@/api/types"

export const employeesKey = ["employees"] as const
export const managersKey = ["managers"] as const
export const shiftTypesKey = ["shift-types"] as const
export const settingsKey = ["settings"] as const
export const nonWorkingDatesKey = ["non-working-dates"] as const

export function useEmployeesQuery() {
  return useQuery({
    queryKey: employeesKey,
    queryFn: async () => {
      const { data } = await apiClient.get<EmployeeResponse[]>("/api/employees")
      return data
    },
  })
}

export function useManagersQuery() {
  return useQuery({
    queryKey: managersKey,
    queryFn: async () => {
      const { data } = await apiClient.get<ManagerResponse[]>("/api/managers")
      return data
    },
  })
}

export function useShiftTypesQuery() {
  return useQuery({
    queryKey: shiftTypesKey,
    queryFn: async () => {
      const { data } =
        await apiClient.get<ShiftTypeResponse[]>("/api/shift-types")
      return data
    },
  })
}

export function useSettingsQuery() {
  return useQuery({
    queryKey: settingsKey,
    queryFn: async () => {
      const { data } = await apiClient.get<SettingsResponse>("/api/settings")
      return data
    },
  })
}

export function useNonWorkingDatesQuery() {
  return useQuery({
    queryKey: nonWorkingDatesKey,
    queryFn: async () => {
      const { data } = await apiClient.get<NonWorkingDateResponse[]>(
        "/api/non-working-dates"
      )
      return data
    },
  })
}
