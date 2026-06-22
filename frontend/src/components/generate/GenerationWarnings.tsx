import { AlertTriangle } from "lucide-react"

import type { GenerationWarnings as GenerationWarningsState } from "@/hooks/useGenerationWarnings"
import { C_MAX, NIGHT_CAP_HOURS } from "@/lib/constants"

type GenerationWarningsProps = GenerationWarningsState & { regime: string }

export function GenerationWarnings({
  nightCapViolation,
  capacityWarning,
  utilizationWarning,
  leaveWarning,
  cpsatTooLarge,
  regime,
}: GenerationWarningsProps) {
  return (
    <>
      {cpsatTooLarge && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          CP-SAT may not finish within the time budget at this size — GA is
          recommended.
        </p>
      )}

      {nightCapViolation && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Shift type “{nightCapViolation.name}” exceeds the {NIGHT_CAP_HOURS}h
          night cap under the current FIVE_DAY regime. Shorten it before
          generating.
        </p>
      )}

      {capacityWarning?.kind === "hard" && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          With {capacityWarning.current} employee(s) and{" "}
          {capacityWarning.sumRs} position(s) per day, the workforce is too
          small to cover all shifts with mandatory rest days. Need at least{" "}
          {capacityWarning.needed} active employee(s). No feasible schedule
          exists — this request will be rejected.
        </p>
      )}

      {capacityWarning?.kind === "tight" && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Workforce is at {capacityWarning.pct}% of theoretical capacity.{" "}
          {regime !== "FIVE_DAY"
            ? `Weekly rest (two consecutive days off each week) limits each employee to ${C_MAX} of every ${C_MAX + 2} days — this configuration`
            : "With nearly every employee needed every weekday, there is little slack — this configuration"}{" "}
          may not produce a feasible schedule. Consider adding employees or
          reducing staffing requirements.
        </p>
      )}

      {utilizationWarning?.kind === "over" && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Total staffed hours (~{utilizationWarning.demandHours}h) exceed the
          workforce's total contracted hours (~
          {utilizationWarning.contractedHours}h) for this period. Every
          staffed slot must be filled (exact staffing) and no employee may
          exceed their contracted norm (no overtime), so no feasible schedule
          exists — this request will be rejected. Reduce staffing or shift
          lengths, or add at least {utilizationWarning.extraNeeded} more
          full-time employee(s).
        </p>
      )}

      {utilizationWarning?.kind === "under" && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Current staffing schedules ~{utilizationWarning.avgAvailable}h per
          employee, below the ~{utilizationWarning.avgContracted}h contracted
          for this period. Some under-utilization can be unavoidable,{" "}
          {regime !== "FIVE_DAY"
            ? `because mandatory rest caps each employee at ${C_MAX} of every ${C_MAX + 2} days`
            : "given the staffing demand and workforce size"}
          . Adding staffing per shift only raises this if your workforce has
          spare capacity — past that limit the schedule becomes infeasible.
          Otherwise the shortfall is structural and the small soft-constraint
          penalty is expected.
        </p>
      )}

      {leaveWarning?.definite && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {leaveWarning.totalEmployeesWithLeave} employee(s) have approved
          leave in this period — on the busiest day, {leaveWarning.peakLeave}{" "}
          are off simultaneously, leaving only {leaveWarning.peakEffective}{" "}
          available for the {leaveWarning.sumRs} position(s) that must be
          filled by distinct employees. No feasible schedule exists — this
          request will be rejected. Adjust the overlapping leave, reduce
          staffing, or add employees.
        </p>
      )}

      {leaveWarning && !leaveWarning.definite && (
        <p
          role="alert"
          className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {leaveWarning.totalEmployeesWithLeave} employee(s) have approved
          leave in this period — peak overlap is {leaveWarning.peakLeave},
          leaving {leaveWarning.peakEffective} employee(s) available on the
          busiest day. Verify coverage is sufficient.
        </p>
      )}
    </>
  )
}
