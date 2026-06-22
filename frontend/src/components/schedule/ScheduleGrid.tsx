import { useMemo, useState } from "react"
import { eachDayOfInterval, format, parseISO } from "date-fns"

import type { ScheduleDetail } from "@/api/types"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { ArrowUpDown } from "lucide-react"
import { formatScheduleDay, formatTime } from "@/lib/format"
import {
  classifyShift,
  shiftCellClasses,
  shiftDurationHours,
  shiftInitial,
  type ShiftCategory,
} from "@/lib/shifts"
import { cn } from "@/lib/utils"

type SortKey = "name" | "hours"

interface ScheduleGridProps {
  schedule: ScheduleDetail
}

interface ShiftMeta {
  name: string
  category: ShiftCategory
  start: string
  end: string
}

export function ScheduleGrid({ schedule }: ScheduleGridProps) {
  const [sortKey, setSortKey] = useState<SortKey>("name")

  const days = useMemo(() => {
    // format in local time 
    return eachDayOfInterval({
      start: parseISO(schedule.start_date),
      end: parseISO(schedule.end_date),
    }).map((date) => format(date, "yyyy-MM-dd"))
  }, [schedule.start_date, schedule.end_date])

  const shiftMeta = useMemo(() => {
    const map = new Map<number, ShiftMeta>()
    for (const shift of schedule.shift_types) {
      map.set(shift.id, {
        name: shift.name,
        category: classifyShift(shift),
        start: shift.start_time,
        end: shift.end_time,
      })
    }
    return map
  }, [schedule.shift_types])

  const grid = useMemo(() => {
    const map = new Map<number, Map<string, number | null>>()
    for (const assignment of schedule.assignments) {
      if (!map.has(assignment.employee_id)) {
        map.set(assignment.employee_id, new Map())
      }
      map.get(assignment.employee_id)!.set(assignment.date, assignment.shift_type_id)
    }
    return map
  }, [schedule.assignments])

  const hoursByEmployee = useMemo(() => {
    const totals = new Map<number, number>()
    for (const assignment of schedule.assignments) {
      if (assignment.shift_type_id == null) continue
      const meta = shiftMeta.get(assignment.shift_type_id)
      if (!meta) continue
      const hours = shiftDurationHours(meta.start, meta.end)
      totals.set(
        assignment.employee_id,
        (totals.get(assignment.employee_id) ?? 0) + hours
      )
    }
    return totals
  }, [schedule.assignments, shiftMeta])

  const sortedEmployees = useMemo(() => {
    return [...schedule.employees].sort((a, b) => {
      if (sortKey === "hours") {
        const diff =
          (hoursByEmployee.get(b.id) ?? 0) - (hoursByEmployee.get(a.id) ?? 0)
        if (diff !== 0) return diff
      }
      return a.name.localeCompare(b.name)
    })
  }, [schedule.employees, sortKey, hoursByEmployee])

  return (
    <div className="relative max-h-[70vh] overflow-auto rounded-lg border">
      <table className="border-collapse text-sm">
        <thead>
          <tr>
            <th
              scope="col"
              className="sticky left-0 top-0 z-30 min-w-[12rem] border-b border-r bg-background px-3 py-2 text-left"
            >
              <button
                type="button"
                className="flex items-center gap-1 font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                onClick={() =>
                  setSortKey((key) => (key === "name" ? "hours" : "name"))
                }
                aria-label={`Sort by ${sortKey === "name" ? "hours" : "name"}`}
              >
                Employee
                <ArrowUpDown className="h-3.5 w-3.5" aria-hidden />
                <span className="text-xs font-normal text-muted-foreground">
                  ({sortKey})
                </span>
              </button>
            </th>
            {days.map((day) => (
              <th
                key={day}
                scope="col"
                className="sticky top-0 z-20 min-w-[3rem] border-b bg-background px-1 py-2 text-center text-xs font-medium"
              >
                {formatScheduleDay(day)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedEmployees.map((employee) => {
            const row = grid.get(employee.id)
            return (
              <tr key={employee.id} className="group">
                <th
                  scope="row"
                  className="sticky left-0 z-10 min-w-[12rem] border-b border-r bg-background px-3 py-2 text-left font-medium group-hover:bg-muted/60"
                >
                  <span className="block truncate">{employee.name}</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {(hoursByEmployee.get(employee.id) ?? 0).toFixed(0)} h
                  </span>
                </th>
                {days.map((day) => {
                  const shiftId = row?.get(day) ?? null
                  const meta = shiftId != null ? shiftMeta.get(shiftId) : null

                  if (!meta) {
                    return (
                      <td
                        key={day}
                        className={cn(
                          "border-b px-1 py-2 text-center",
                          shiftCellClasses("OFF")
                        )}
                      >
                        —
                      </td>
                    )
                  }

                  return (
                    <Tooltip key={day}>
                      <TooltipTrigger asChild>
                        <td
                          className={cn(
                            "border-b px-1 py-2 text-center font-medium group-hover:brightness-95",
                            shiftCellClasses(meta.category)
                          )}
                        >
                          {shiftInitial(meta.category, meta.name)}
                        </td>
                      </TooltipTrigger>
                      <TooltipContent>
                        {meta.name}: {formatTime(meta.start)} –{" "}
                        {formatTime(meta.end)}
                      </TooltipContent>
                    </Tooltip>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
