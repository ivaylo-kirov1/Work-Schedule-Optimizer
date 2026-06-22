import { useMemo } from "react"
import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { ScheduleDetail, SoftViolations } from "@/api/types"
import { shiftDurationHours } from "@/lib/shifts"

interface HoursChartProps {
  schedule: ScheduleDetail
}

const SOFT_LABELS: Record<keyof SoftViolations, string> = {
  S1: "Preferences (S1)",
  S2: "Hours deviation (S2)",
  S3: "Long shifts (S3)",
  S4: "Weekend fairness (S4)",
  S5: "Night fairness (S5)",
  S6: "Hours spread (S6)",
}

const DONUT_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-2)",
]


export function HoursPerEmployeeChart({ schedule }: HoursChartProps) {
  const data = useMemo(() => {
    const shiftHours = new Map<number, number>()
    for (const shift of schedule.shift_types) {
      shiftHours.set(
        shift.id,
        shiftDurationHours(shift.start_time, shift.end_time)
      )
    }

    const totals = new Map<number, number>()
    for (const assignment of schedule.assignments) {
      if (assignment.shift_type_id == null) continue
      const hours = shiftHours.get(assignment.shift_type_id) ?? 0
      totals.set(
        assignment.employee_id,
        (totals.get(assignment.employee_id) ?? 0) + hours
      )
    }

    return schedule.employees
      .map((employee) => ({
        name: employee.name,
        hours: Math.round(totals.get(employee.id) ?? 0),
      }))
      .sort((a, b) => b.hours - a.hours)
  }, [schedule])

  if (data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No assignment data.</p>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 44)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
      >
        <XAxis type="number" tick={{ fontSize: 12 }} />
        <YAxis
          type="category"
          dataKey="name"
          width={110}
          tick={{ fontSize: 12 }}
          interval={0}
        />
        <RechartsTooltip
          formatter={(value) => [`${value} h`, "Scheduled hours"]}
        />
        <Bar dataKey="hours" fill="var(--chart-1)" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

interface SoftChartProps {
  soft: SoftViolations
}

export function SoftViolationsChart({ soft }: SoftChartProps) {
  const data = useMemo(() => {
    return (Object.keys(SOFT_LABELS) as (keyof SoftViolations)[])
      .map((key) => ({ name: SOFT_LABELS[key], value: soft[key] }))
      .filter((entry) => entry.value > 0)
  }, [soft])

  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No soft-constraint violations.
      </p>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          innerRadius={50}
          outerRadius={80}
          paddingAngle={2}
        >
          {data.map((entry, index) => (
            <Cell
              key={entry.name}
              fill={DONUT_COLORS[index % DONUT_COLORS.length]}
            />
          ))}
        </Pie>
        <RechartsTooltip />
        <Legend
          verticalAlign="bottom"
          height={56}
          wrapperStyle={{ fontSize: "12px" }}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
