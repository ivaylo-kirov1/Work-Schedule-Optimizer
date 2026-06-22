import { format, parseISO } from "date-fns"

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const

export const WEEKDAYS: { value: number; short: string; long: string }[] = [
  { value: 0, short: "Mon", long: "Monday" },
  { value: 1, short: "Tue", long: "Tuesday" },
  { value: 2, short: "Wed", long: "Wednesday" },
  { value: 3, short: "Thu", long: "Thursday" },
  { value: 4, short: "Fri", long: "Friday" },
  { value: 5, short: "Sat", long: "Saturday" },
  { value: 6, short: "Sun", long: "Sunday" },
]

export function weekdayLabel(day: number): string {
  return WEEKDAY_LABELS[day] ?? String(day)
}

/** drops seconds from a "HH:MM:SS" time string */
export function formatTime(time: string | null | undefined): string {
  if (!time) return ""
  return time.slice(0, 5)
}

/** formats an ISO date ("YYYY-MM-DD") as for exmaple "Mon 1" for grid headers */
export function formatScheduleDay(isoDate: string): string {
  return format(parseISO(isoDate), "EEE d")
}

/** formats an ISO date as for example 1 Jun 2026*/
export function formatLongDate(isoDate: string): string {
  return format(parseISO(isoDate), "d MMM yyyy")
}

/** formats an ISO datetime - 1 Jun 2026, 14:30 */
export function formatDateTime(isoDateTime: string): string {
  return format(parseISO(isoDateTime), "d MMM yyyy, HH:mm")
}

/** formats a YYYY-MM month string - June 2026 */
export function formatMonthLabel(yearMonth: string): string {
  const [year, month] = yearMonth.split("-").map(Number)
  if (!year || !month) return yearMonth
  return format(new Date(year, month - 1, 1), "MMMM yyyy")
}

/** elapsed seconds - MM:SS. */
export function formatElapsed(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
}


export function monthRange(start: string, end: string): string[] {
  if (!/^\d{4}-\d{2}$/.test(start) || !/^\d{4}-\d{2}$/.test(end)) return []
  const [startYear, startMonth] = start.split("-").map(Number)
  const [endYear, endMonth] = end.split("-").map(Number)
  if (startYear > endYear || (startYear === endYear && startMonth > endMonth)) {
    return []
  }
  const months: string[] = []
  let year = startYear
  let month = startMonth
  while (year < endYear || (year === endYear && month <= endMonth)) {
    months.push(`${year}-${String(month).padStart(2, "0")}`)
    month += 1
    if (month > 12) {
      month = 1
      year += 1
    }
  }
  return months
}
