import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { Algorithm, GenerateResponse } from "@/api/types"
import {
  useEmployeesQuery,
  useNonWorkingDatesQuery,
  useSettingsQuery,
  useShiftTypesQuery,
} from "@/api/queries"
import { InfoTooltip } from "@/components/InfoTooltip"
import { PageHeader } from "@/components/PageHeader"
import { GeneratingView } from "@/components/generate/GeneratingView"
import { GenerationWarnings } from "@/components/generate/GenerationWarnings"
import { PreGenerationChecklist } from "@/components/generate/PreGenerationChecklist"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useToast } from "@/hooks/useToast"
import { useGenerationWarnings } from "@/hooks/useGenerationWarnings"
import {
  formatLongDate,
  formatMonthLabel,
  monthRange,
  weekdayLabel,
} from "@/lib/format"

const TASK_STORAGE_KEY = "activeGenerationTaskId"
const TASK_START_KEY = "activeGenerationStartTime"

const generateSchema = z
  .object({
    start_month: z.string().regex(/^\d{4}-\d{2}$/, "Select a start month"),
    end_month: z.string().regex(/^\d{4}-\d{2}$/, "Select an end month"),
    algorithm: z.enum(["GA", "CP_SAT"]),
    monthly_norms: z.record(z.string(), z.number().int().gte(1).lte(300)),
    staffing: z.record(z.string(), z.number().int().gte(1)),
  })
  .refine((values) => values.start_month <= values.end_month, {
    message: "Start month must not be after end month",
    path: ["end_month"],
  })

type GenerateFormValues = z.infer<typeof generateSchema>

export function GeneratePage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [taskId, setTaskIdState] = useState<string | null>(
    () => sessionStorage.getItem(TASK_STORAGE_KEY)
  )
  const [startedAt, setStartedAt] = useState<number>(
    () => Number(sessionStorage.getItem(TASK_START_KEY) ?? Date.now())
  )

  const setTaskId = useCallback((id: string | null) => {
    if (id) {
      const now = Date.now()
      sessionStorage.setItem(TASK_STORAGE_KEY, id)
      sessionStorage.setItem(TASK_START_KEY, String(now))
      setStartedAt(now)
    } else {
      sessionStorage.removeItem(TASK_STORAGE_KEY)
      sessionStorage.removeItem(TASK_START_KEY)
    }
    setTaskIdState(id)
  }, [])

  const { data: employees } = useEmployeesQuery()
  const { data: shiftTypes } = useShiftTypesQuery()
  const { data: settings } = useSettingsQuery()
  const { data: nonWorkingDates } = useNonWorkingDatesQuery()

  const activeEmployees = useMemo(
    () => (employees ?? []).filter((emp) => emp.is_active),
    [employees]
  )
  const activeShiftTypes = useMemo(
    () => (shiftTypes ?? []).filter((shift) => shift.is_active),
    [shiftTypes]
  )

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<GenerateFormValues>({
    resolver: zodResolver(generateSchema),
    defaultValues: {
      start_month: "",
      end_month: "",
      algorithm: "GA",
      monthly_norms: {},
      staffing: {},
    },
  })

  const startMonth = watch("start_month")
  const endMonth = watch("end_month")
  const algorithm = watch("algorithm")

  const months = useMemo(
    () => monthRange(startMonth, endMonth),
    [startMonth, endMonth]
  )

  // seed staffing inputs for active shift types once they load
  const seededStaffing = useRef(false)
  useEffect(() => {
    if (seededStaffing.current || activeShiftTypes.length === 0) return
    for (const shift of activeShiftTypes) {
      setValue(`staffing.${shift.id}`, 1)
    }
    seededStaffing.current = true
  }, [activeShiftTypes, setValue])

  const regime = settings?.regime ?? "SUMMARIZED"
  const offWeekdays = settings?.off_weekdays ?? []

  const datesInPeriod = useMemo(() => {
    if (months.length === 0 || !nonWorkingDates) return []
    const monthSet = new Set(months)
    return nonWorkingDates
      .filter((entry) => monthSet.has(entry.date.slice(0, 7)))
      .sort((a, b) => a.date.localeCompare(b.date))
  }, [months, nonWorkingDates])

  const staffingValues = watch("staffing")
  const monthlyNormsValues = watch("monthly_norms")

  const warnings = useGenerationWarnings({
    activeEmployees,
    activeShiftTypes,
    months,
    regime,
    offWeekdays,
    nonWorkingDates,
    staffingValues,
    monthlyNormsValues,
    algorithm,
  })

  const mutation = useMutation({
    mutationFn: async (values: GenerateFormValues) => {
      const body = {
        algorithm: values.algorithm as Algorithm,
        start_month: values.start_month,
        end_month: values.end_month,
        monthly_norms: months.reduce<Record<string, number>>((acc, month) => {
          acc[month] = Number(values.monthly_norms[month])
          return acc
        }, {}),
        staffing: activeShiftTypes.reduce<Record<string, number>>(
          (acc, shift) => {
            acc[String(shift.id)] = Number(values.staffing[shift.id])
            return acc
          },
          {}
        ),
      }
      const { data } = await apiClient.post<GenerateResponse>(
        "/api/schedules/generate",
        body
      )
      return data
    },
    onSuccess: (data) => {
      setTaskId(data.task_id)
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not start generation",
        description: extractErrorMessage(error),
      })
    },
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  const handleFailed = useCallback(
    (message: string) => {
      setTaskId(null)
      toast({
        variant: "destructive",
        title: "Generation failed",
        description: message,
      })
    },
    [setTaskId, toast]
  )

  const handleCancel = useCallback(() => {
    setTaskId(null)
    toast({ title: "Generation cancelled" })
  }, [setTaskId, toast])

  const handleCompleted = useCallback(() => {
    setTaskId(null)
    navigate("/manager/schedule", { replace: true })
  }, [setTaskId, navigate])

  if (taskId) {
    return (
      <div className="max-w-2xl">
        <PageHeader title="Generate Schedule" />
        <GeneratingView
          taskId={taskId}
          startedAt={startedAt}
          onCompleted={handleCompleted}
          onFailed={handleFailed}
          onCancel={handleCancel}
        />
      </div>
    )
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className="max-w-3xl">
        <PageHeader
          title="Generate Schedule"
          description="Configure and run the optimizer for a planning period."
        />

        <form onSubmit={onSubmit} className="space-y-6" noValidate>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Planning period</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="start-month">Start month</Label>
                <Input
                  id="start-month"
                  type="month"
                  aria-invalid={Boolean(errors.start_month)}
                  aria-describedby={
                    errors.start_month ? "start-month-error" : undefined
                  }
                  {...register("start_month")}
                />
                {errors.start_month && (
                  <p
                    id="start-month-error"
                    role="alert"
                    className="text-sm text-destructive"
                  >
                    {errors.start_month.message}
                  </p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="end-month">End month</Label>
                <Input
                  id="end-month"
                  type="month"
                  aria-invalid={Boolean(errors.end_month)}
                  aria-describedby={
                    errors.end_month ? "end-month-error" : undefined
                  }
                  {...register("end_month")}
                />
                {errors.end_month && (
                  <p
                    id="end-month-error"
                    role="alert"
                    className="text-sm text-destructive"
                  >
                    {errors.end_month.message}
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {months.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  Monthly norms
                  <InfoTooltip text="Enter the official ministry norm for this month. Subtract 8h for each company-specific closure day you added." />
                </CardTitle>
                <CardDescription>
                  One value per month in the planning period.
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                {months.map((month) => (
                  <div key={month} className="space-y-1.5">
                    <Label htmlFor={`norm-${month}`}>
                      {formatMonthLabel(month)}
                    </Label>
                    <Input
                      id={`norm-${month}`}
                      type="number"
                      min={1}
                      max={300}
                      placeholder="e.g. 168"
                      aria-invalid={Boolean(errors.monthly_norms?.[month])}
                      aria-describedby={
                        errors.monthly_norms?.[month]
                          ? `norm-${month}-error`
                          : undefined
                      }
                      {...register(`monthly_norms.${month}`, {
                        valueAsNumber: true,
                      })}
                    />
                    {errors.monthly_norms?.[month] && (
                      <p
                        id={`norm-${month}-error`}
                        role="alert"
                        className="text-sm text-destructive"
                      >
                        Enter a value between 1 and 300.
                      </p>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                Staffing per shift
                <InfoTooltip text="Exact number of employees required on every working day in the period for this shift type." />
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2">
              {activeShiftTypes.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No active shift types. Add at least one before generating.
                </p>
              ) : (
                activeShiftTypes.map((shift) => (
                  <div key={shift.id} className="space-y-1.5">
                    <Label htmlFor={`staffing-${shift.id}`}>{shift.name}</Label>
                    <Input
                      id={`staffing-${shift.id}`}
                      type="number"
                      min={1}
                      aria-invalid={Boolean(errors.staffing?.[shift.id])}
                      aria-describedby={
                        errors.staffing?.[shift.id]
                          ? `staffing-${shift.id}-error`
                          : undefined
                      }
                      {...register(`staffing.${shift.id}`, {
                        valueAsNumber: true,
                      })}
                    />
                    {errors.staffing?.[shift.id] && (
                      <p
                        id={`staffing-${shift.id}-error`}
                        role="alert"
                        className="text-sm text-destructive"
                      >
                        Enter at least 1.
                      </p>
                    )}
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                Algorithm
                <InfoTooltip text="GA works for all team sizes and always returns a schedule. CP-SAT is exact but may time out above ~15 employees." />
              </CardTitle>
            </CardHeader>
            <CardContent>
              <RadioGroup
                value={algorithm}
                onValueChange={(value) =>
                  setValue("algorithm", value as Algorithm)
                }
              >
                <label
                  htmlFor="algo-ga"
                  className="flex items-center gap-3 rounded-md border p-3 text-sm"
                >
                  <RadioGroupItem value="GA" id="algo-ga" />
                  GA (recommended)
                </label>
                <label
                  htmlFor="algo-cpsat"
                  className="flex items-center gap-3 rounded-md border p-3 text-sm"
                >
                  <RadioGroupItem value="CP_SAT" id="algo-cpsat" />
                  CP-SAT
                </label>
              </RadioGroup>
            </CardContent>
          </Card>

          <GenerationWarnings {...warnings} regime={regime} />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Context</CardTitle>
              <CardDescription>
                Current company settings applied during generation.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-medium">Regime:</span>
                <Badge variant="outline">{regime}</Badge>
              </div>
              <div>
                <span className="font-medium">Weekly off days:</span>{" "}
                {offWeekdays.length === 0
                  ? "none (24/7)"
                  : offWeekdays.map(weekdayLabel).join(", ")}
              </div>
              <div>
                <span className="font-medium">Active employees:</span>{" "}
                {activeEmployees.length}
              </div>
              <div>
                <span className="font-medium">Non-working dates in period:</span>{" "}
                {months.length === 0 ? (
                  <span className="text-muted-foreground">
                    select a period to view
                  </span>
                ) : datesInPeriod.length === 0 ? (
                  "none"
                ) : (
                  <ul className="mt-1 list-inside list-disc text-muted-foreground">
                    {datesInPeriod.map((entry) => (
                      <li key={entry.id}>
                        {formatLongDate(entry.date)}
                        {entry.note ? ` — ${entry.note}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </CardContent>
          </Card>

          <PreGenerationChecklist />

          <Button type="submit" size="lg" disabled={mutation.isPending}>
            {mutation.isPending ? "Starting…" : "Generate schedule"}
          </Button>
        </form>
      </div>
    </TooltipProvider>
  )
}
