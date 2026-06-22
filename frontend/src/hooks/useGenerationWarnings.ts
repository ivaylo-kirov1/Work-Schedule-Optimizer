import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"

import { apiClient } from "@/api/client"
import type {
  EmployeeResponse,
  LeaveRequestResponse,
  NonWorkingDateResponse,
  ShiftTypeResponse,
} from "@/api/types"
import {
  C_MAX,
  CP_SAT_EMPLOYEE_THRESHOLD,
  DELTA_PER_MONTH,
  NIGHT_CAP_HOURS,
} from "@/lib/constants"
import { isNightShift, shiftDurationHours } from "@/lib/shifts"

interface UseGenerationWarningsParams {
  activeEmployees: EmployeeResponse[]
  activeShiftTypes: ShiftTypeResponse[]
  months: string[]
  regime: string
  offWeekdays: number[]
  nonWorkingDates: NonWorkingDateResponse[] | undefined
  staffingValues: Record<string, number>
  monthlyNormsValues: Record<string, number>
  algorithm: string
}

export function useGenerationWarnings({
  activeEmployees,
  activeShiftTypes,
  months,
  regime,
  offWeekdays,
  nonWorkingDates,
  staffingValues,
  monthlyNormsValues,
  algorithm,
}: UseGenerationWarningsParams) {
  const cpsatTooLarge =
    algorithm === "CP_SAT" &&
    activeEmployees.length > CP_SAT_EMPLOYEE_THRESHOLD

  const nightCapViolation = useMemo(() => {
    if (regime !== "FIVE_DAY") return null
    return (
      activeShiftTypes.find(
        (shift) =>
          isNightShift(shift.start_time, shift.end_time) &&
          shiftDurationHours(shift.start_time, shift.end_time) > NIGHT_CAP_HOURS
      ) ?? null
    )
  }, [regime, activeShiftTypes])

  // Primitive fingerprints derived from the watched objects so useMemo deps
  // detect changes — react-hook-form can return the same object reference with
  // mutated properties, making object deps always appear unchanged.
  const staffingKey = activeShiftTypes.map(s => String(staffingValues?.[s.id] ?? "")).join(",")
  const normValuesKey = months.map(m => String(monthlyNormsValues?.[m] ?? "")).join(",")

  // null → no warning; { kind: "hard", … } → definitively infeasible; { kind: "tight", … } → close to limit
  const capacityWarning = useMemo(() => {
    if (activeEmployees.length === 0 || activeShiftTypes.length === 0)
      return null
    const sumRs = activeShiftTypes.reduce(
      (acc, shift) => acc + (Number(staffingValues[shift.id]) || 0),
      0
    )
    if (sumRs === 0) return null
    const n = activeEmployees.length
    const isFiveDay = regime === "FIVE_DAY"
    const feasible = isFiveDay
      ? n >= sumRs
      : n * C_MAX >= sumRs * (C_MAX + 2)
    if (!feasible) {
      const minEmployees = isFiveDay
        ? sumRs
        : Math.ceil((sumRs * (C_MAX + 2)) / C_MAX)
      return { kind: "hard" as const, current: n, needed: minEmployees, sumRs }
    }
    const ratio = isFiveDay
      ? sumRs / n
      : (sumRs * (C_MAX + 2)) / (n * C_MAX)
    if (ratio <= 0.85) return null
    return { kind: "tight" as const, pct: Math.round(ratio * 100) }
  }, [activeEmployees.length, activeShiftTypes, staffingKey, regime])

  // The solver loads approved leave as a hard constraint — employees on leave
  // cannot be scheduled. Approved leave also reduces each employee's contracted
  // norm (see utilizationWarning), so this query is read by both that memo and
  // leaveWarning below.
  const { data: approvedLeave } = useQuery({
    queryKey: ["leave-requests", "manager", "APPROVED"],
    queryFn: async () => {
      const { data } = await apiClient.get<LeaveRequestResponse[]>(
        "/api/leave-requests",
        { params: { status: "APPROVED" } }
      )
      return data
    },
    enabled: months.length > 0,
  })

  const utilizationWarning = useMemo(() => {
    if (months.length === 0 || activeShiftTypes.length === 0 || activeEmployees.length === 0) return null

    // Only compute when every month has a valid norm — a partial sum skews the comparison
    const allNormsFilled = months.every((month) => {
      const val = Number(monthlyNormsValues[month])
      return !isNaN(val) && val > 0
    })
    if (!allNormsFilled) return null

    const mPeriod = months.reduce((acc, month) => acc + Number(monthlyNormsValues[month]), 0)

    const nonWorkingSet = new Set(nonWorkingDates?.map((d) => d.date) ?? [])
    const [startYear, startMonthIdx] = months[0].split("-").map(Number)
    const lastMonth = months[months.length - 1]
    const [endYear, endMonthIdx] = lastMonth.split("-").map(Number)
    // Use local dates to avoid UTC-offset day shifting
    const start = new Date(startYear, startMonthIdx - 1, 1)
    const end = new Date(endYear, endMonthIdx, 0) // last day of end month
    let workingDays = 0
    const cur = new Date(start)
    while (cur <= end) {
      const dow = (cur.getDay() + 6) % 7 // 0=Mon … 6=Sun
      const dateStr = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}-${String(cur.getDate()).padStart(2, "0")}`
      if (!offWeekdays.includes(dow) && !nonWorkingSet.has(dateStr)) workingDays++
      cur.setDate(cur.getDate() + 1)
    }
    if (workingDays === 0) return null

    // Approved leave reduces each employee's contracted norm by hours_per_week/5
    // for every qualifying leave day: Mon–Fri on the statutory five-day calendar
    // (НРВПО чл. 9б) AND not an explicit company non-working date. This basis is
    // Mon–Fri regardless of regime — it does NOT use offWeekdays. Mirrors backend
    // pre-flight validation #13 (cap = Σ max(0, M_e − reduction_e)). While the
    // approvedLeave query is still loading, reductions stay zero. Walk the period
    // with local dates and match leave via "YYYY-MM-DD" string comparison (same
    // pattern as leaveWarning) to avoid UTC-offset day shifting from new Date().
    const activeEmployeeIds = new Set(activeEmployees.map((emp) => emp.id))
    const periodLeave = (approvedLeave ?? []).filter((leave) =>
      activeEmployeeIds.has(leave.employee_id)
    )
    const reductionById = new Map<number, number>()
    if (periodLeave.length > 0) {
      const hoursById = new Map(activeEmployees.map((emp) => [emp.id, emp.hours_per_week]))
      const leaveDayKeys = new Set<string>()
      const leaveCur = new Date(start)
      while (leaveCur <= end) {
        const leaveDow = (leaveCur.getDay() + 6) % 7 // 0=Mon … 6=Sun
        const leaveDateStr = `${leaveCur.getFullYear()}-${String(leaveCur.getMonth() + 1).padStart(2, "0")}-${String(leaveCur.getDate()).padStart(2, "0")}`
        if (leaveDow < 5 && !nonWorkingSet.has(leaveDateStr)) {
          for (const leave of periodLeave) {
            // Dedup (employee, day): the Set key absorbs overlapping requests
            if (leave.start_date <= leaveDateStr && leave.end_date >= leaveDateStr) {
              leaveDayKeys.add(`${leave.employee_id}|${leaveDateStr}`)
            }
          }
        }
        leaveCur.setDate(leaveCur.getDate() + 1)
      }
      for (const key of leaveDayKeys) {
        const empId = Number(key.slice(0, key.indexOf("|")))
        const hoursPerWeek = hoursById.get(empId) ?? 0
        reductionById.set(empId, (reductionById.get(empId) ?? 0) + hoursPerWeek / 5)
      }
    }

    const totalContracted = activeEmployees.reduce(
      (acc, emp) =>
        acc +
        Math.max(0, mPeriod * (emp.hours_per_week / 40) - (reductionById.get(emp.id) ?? 0)),
      0
    )

    const sumRs = activeShiftTypes.reduce((acc, shift) => acc + (Number(staffingValues[shift.id]) || 0), 0)
    const totalAvailable = activeShiftTypes.reduce((acc, shift) => {
      const rs = Number(staffingValues[shift.id]) || 0
      const dur = shiftDurationHours(shift.start_time, shift.end_time)
      return acc + rs * dur * workingDays
    }, 0)

    // Over-demand: exact staffing (H6) forces every staffed slot to be filled,
    // while no-overtime (H5) caps each employee at their contracted norm. If the
    // total staffed hours exceed total contracted hours, no feasible schedule
    // exists — the backend rejects this with HTTP 422. Checked first because it
    // is a definitive infeasibility, not a soft under-utilization heuristic.
    if (totalAvailable > totalContracted) {
      const extraNeeded = Math.ceil((totalAvailable - totalContracted) / mPeriod)
      return {
        kind: "over" as const,
        demandHours: Math.round(totalAvailable),
        contractedHours: Math.round(totalContracted),
        extraNeeded,
      }
    }

    const avgContractedPerEmployee = totalContracted / activeEmployees.length

    // Raw share: total slots distributed evenly — bottleneck when R_s is too low
    const rawSharePerEmployee = totalAvailable / activeEmployees.length

    // Rest-constrained effective max: H4/H9 cap each employee to C_MAX/(C_MAX+2)
    // working days in the SUMMARIZED regime. In FIVE_DAY, workingDays already
    // excludes weekends and the weekly-rest constraint is satisfied by them, so
    // no haircut applies (mirrors capacityWarning's regime branch).
    const avgShiftDuration = sumRs > 0 ? totalAvailable / (workingDays * sumRs) : 0
    const effectiveWorkingDays =
      regime === "FIVE_DAY"
        ? workingDays
        : Math.floor((workingDays * C_MAX) / (C_MAX + 2))
    const effectiveHoursPerEmployee = effectiveWorkingDays * avgShiftDuration

    // The binding constraint is whichever gives the lower estimate
    const estimatedHoursPerEmployee = Math.min(rawSharePerEmployee, effectiveHoursPerEmployee)

    // The S2 soft penalty only charges hours below a tolerance band:
    // contracted − DELTA_PER_MONTH × months. Only warn when the estimate falls
    // below that band, not merely below the raw contracted total.
    const underThreshold =
      avgContractedPerEmployee - DELTA_PER_MONTH * months.length
    if (estimatedHoursPerEmployee >= underThreshold) return null

    return {
      kind: "under" as const,
      avgAvailable: Math.round(estimatedHoursPerEmployee),
      avgContracted: Math.round(avgContractedPerEmployee),
    }
  }, [months, activeShiftTypes, activeEmployees, normValuesKey, staffingKey, offWeekdays, nonWorkingDates, regime, approvedLeave])

  const leaveWarning = useMemo(() => {
    if (months.length === 0 || activeEmployees.length === 0) return null
    if (!approvedLeave || approvedLeave.length === 0) return null

    const sumRs = activeShiftTypes.reduce(
      (acc, shift) => acc + (Number(staffingValues[shift.id]) || 0),
      0
    )
    if (sumRs === 0) return null

    const [startYear, startMonthIdx] = months[0].split("-").map(Number)
    const lastMonth = months[months.length - 1]
    const [endYear, endMonthIdx] = lastMonth.split("-").map(Number)
    // Use local dates to avoid UTC-offset day shifting
    const periodStart = new Date(startYear, startMonthIdx - 1, 1)
    const periodEnd = new Date(endYear, endMonthIdx, 0) // last day of end month

    // Only active employees' leave blocks scheduling — the backend's validator
    // counts leave from active employees alone, so deactivated employees' leave
    // must be excluded here to match.
    const activeEmployeeIds = new Set(activeEmployees.map((emp) => emp.id))
    const overlapping = approvedLeave.filter((leave) => {
      if (!activeEmployeeIds.has(leave.employee_id)) return false
      const leaveStart = new Date(leave.start_date)
      const leaveEnd = new Date(leave.end_date)
      return leaveStart <= periodEnd && leaveEnd >= periodStart
    })
    if (overlapping.length === 0) return null

    const nonWorkingSet = new Set(nonWorkingDates?.map((d) => d.date) ?? [])
    let peakLeave = 0
    const cur = new Date(periodStart)
    while (cur <= periodEnd) {
      const dow = (cur.getDay() + 6) % 7 // 0=Mon … 6=Sun
      const dateStr = `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}-${String(cur.getDate()).padStart(2, "0")}`
      if (!offWeekdays.includes(dow) && !nonWorkingSet.has(dateStr)) {
        const employeesOnLeave = new Set<number>()
        for (const leave of overlapping) {
          if (leave.start_date <= dateStr && leave.end_date >= dateStr) {
            employeesOnLeave.add(leave.employee_id)
          }
        }
        if (employeesOnLeave.size > peakLeave) peakLeave = employeesOnLeave.size
      }
      cur.setDate(cur.getDate() + 1)
    }
    if (peakLeave === 0) return null

    const totalEmployeesWithLeave = new Set(overlapping.map((l) => l.employee_id)).size
    const peakEffective = activeEmployees.length - peakLeave
    return {
      peakLeave,
      peakEffective,
      totalEmployeesWithLeave,
      sumRs,
      definite: peakEffective < sumRs,
    }
  }, [
    months,
    activeShiftTypes,
    activeEmployees,
    staffingKey,
    approvedLeave,
    offWeekdays,
    nonWorkingDates,
  ])

  return { nightCapViolation, capacityWarning, utilizationWarning, leaveWarning, cpsatTooLarge }
}

export type GenerationWarnings = ReturnType<typeof useGenerationWarnings>
