export type ShiftCategory = "DAY" | "EVENING" | "NIGHT" | "OFF" | "OTHER"

interface ClassifiableShift {
  name: string
  start_time: string
}

/**  classify a shift type into a display category, name match takes precedence*/
export function classifyShift(shift: ClassifiableShift): ShiftCategory {
  const name = shift.name.toLowerCase()
  if (name.includes("night")) return "NIGHT"
  if (name.includes("evening")) return "EVENING"
  if (name.includes("day")) return "DAY"

  const startHour = Number(shift.start_time.slice(0, 2))
  if (Number.isNaN(startHour)) return "OTHER"
  if (startHour >= 6 && startHour < 14) return "DAY"
  if (startHour >= 14 && startHour < 21) return "EVENING"
  return "NIGHT"
}

export function shiftCellClasses(category: ShiftCategory): string {
  switch (category) {
    case "DAY":
      return "bg-blue-100 text-blue-900"
    case "EVENING":
      return "bg-orange-100 text-orange-900"
    case "NIGHT":
      return "bg-purple-200 text-purple-900"
    case "OFF":
      return "bg-gray-50 text-gray-400"
    default:
      return "bg-slate-100 text-slate-900"
  }
}

export function shiftInitial(category: ShiftCategory, name: string): string {
  switch (category) {
    case "DAY":
      return "D"
    case "EVENING":
      return "E"
    case "NIGHT":
      return "N"
    case "OFF":
      return "—"
    default:
      return name.charAt(0).toUpperCase()
  }
}

/** hours between a start and end "HH:MM:SS" string, handling midnight crossing */
export function shiftDurationHours(startTime: string, endTime: string): number {
  const startMinutes =
    Number(startTime.slice(0, 2)) * 60 + Number(startTime.slice(3, 5))
  const endMinutes =
    Number(endTime.slice(0, 2)) * 60 + Number(endTime.slice(3, 5))
  let diff = endMinutes - startMinutes
  if (diff <= 0) diff += 24 * 60
  return diff / 60
}


function nightMinutes(startMins: number, endMins: number): number {
  const pieces: [number, number][] = [[0, 360], [1320, 1440], [1440, 1800]]
  return pieces.reduce(
    (total, [ps, pe]) => total + Math.max(0, Math.min(endMins, pe) - Math.max(startMins, ps)),
    0,
  )
}

/** 141(2) KT rule */
export function isNightShift(startTime: string, endTime: string): boolean {
  const startMins =
    Number(startTime.slice(0, 2)) * 60 + Number(startTime.slice(3, 5))
  let endMins = Number(endTime.slice(0, 2)) * 60 + Number(endTime.slice(3, 5))
  if (endMins <= startMins) endMins += 24 * 60
  return nightMinutes(startMins, endMins) >= 4 * 60
}
