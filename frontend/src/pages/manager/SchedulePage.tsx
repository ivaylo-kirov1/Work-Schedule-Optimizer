import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { isAxiosError } from "axios"
import { CalendarDays, Download, Trash2 } from "lucide-react"

import { apiClient, API_BASE_URL, extractErrorMessage, TOKEN_STORAGE_KEY } from "@/api/client"
import type { HardViolations, ScheduleDetail, ScheduleListItem } from "@/api/types"
import { EmptyState } from "@/components/EmptyState"
import { PageHeader } from "@/components/PageHeader"
import {
  HoursPerEmployeeChart,
  SoftViolationsChart,
} from "@/components/schedule/ScheduleCharts"
import { ScheduleGrid } from "@/components/schedule/ScheduleGrid"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useToast } from "@/hooks/useToast"
import { formatLongDate } from "@/lib/format"

function algorithmLabel(algorithm: string): string {
  return algorithm === "CP_SAT" ? "CP-SAT" : algorithm
}

const HARD_CONSTRAINT_LABELS: Record<keyof HardViolations, string> = {
  H1: "double shift on same day",
  H2: "assigned on approved leave",
  H3: "insufficient rest between shifts",
  H4: "too many consecutive working days",
  H5: "employee exceeds contracted hours for period",
  H6: "wrong staffing count",
  H7: "work on mandatory day off",
  H8: "night shift exceeds duration cap",
  H9: "missing two consecutive days off in week",
}

function GridSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, row) => (
        <div key={row} className="flex gap-2">
          <Skeleton className="h-9 w-48 shrink-0" />
          {Array.from({ length: 12 }).map((__, col) => (
            <Skeleton key={col} className="h-9 w-10 shrink-0" />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SchedulePage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [dialogTargetId, setDialogTargetId] = useState<number | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const listQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: async () => {
      const { data } = await apiClient.get<ScheduleListItem[]>("/api/schedules")
      return data
    },
  })

  const detailQuery = useQuery({
    queryKey: ["schedule-detail", selectedId],
    queryFn: async () => {
      const url =
        selectedId == null
          ? "/api/schedules/latest"
          : `/api/schedules/${selectedId}`
      const { data } = await apiClient.get<ScheduleDetail>(url)
      return data
    },
    retry: (failureCount, error) => {
      if (isAxiosError(error) && error.response?.status === 404) return false
      return failureCount < 2
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/api/schedules/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] })
      queryClient.removeQueries({ queryKey: ["schedule-detail", selectedId] })
      setSelectedId(null)
      setDialogOpen(false)
      toast({ title: "Schedule deleted" })
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not delete schedule",
        description: extractErrorMessage(error),
      })
    },
  })

  const schedule = detailQuery.data
  const noScheduleExists =
    isAxiosError(detailQuery.error) &&
    detailQuery.error.response?.status === 404

  const feasible = schedule
    ? Object.values(schedule.hard_violations).every((v) => v === 0)
    : false

  const hardViolationEntries = schedule
    ? Object.entries(schedule.hard_violations).filter(([, count]) => count > 0)
    : []
  const hardViolationTotal = hardViolationEntries.reduce(
    (sum, [, count]) => sum + count,
    0
  )

  const exportExcel = async () => {
    if (!schedule) return
    setIsExporting(true)
    try {
      const token = localStorage.getItem(TOKEN_STORAGE_KEY)
      const response = await fetch(
        `${API_BASE_URL}/api/schedules/${schedule.schedule_id}/export`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        }
      )
      if (!response.ok) {
        if (response.status === 401) {
          localStorage.clear()
          window.location.assign("/login")
          return
        }
        throw new Error(`Export failed (${response.status}).`)
      }
      const blob = await response.blob()
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = objectUrl
      link.download = `schedule-${schedule.schedule_id}.xlsx`
      document.body.appendChild(link)
      link.click()
      link.remove()
      // delay cancellation so the browser can start the download from the URL before it is invalidated.
      setTimeout(() => URL.revokeObjectURL(objectUrl), 100)
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Could not export Excel",
        description: extractErrorMessage(error),
      })
    } finally {
      setIsExporting(false)
    }
  }

  const scheduleOptions = useMemo(() => listQuery.data ?? [], [listQuery.data])

  return (
    <TooltipProvider delayDuration={150}>
      <div>
        <PageHeader
          title="Schedule"
          description="View generated schedules, metrics, and export to Excel."
          actions={
            schedule ? (
              <Button
                variant="outline"
                onClick={exportExcel}
                disabled={isExporting}
              >
                <Download className="h-4 w-4" aria-hidden />
                {isExporting ? "Exporting…" : "Export Excel"}
              </Button>
            ) : undefined
          }
        />

        {scheduleOptions.length > 0 && (
          <div className="mb-6 flex items-center gap-3">
            <Select
              value={selectedId == null ? "latest" : String(selectedId)}
              onValueChange={(value) =>
                setSelectedId(value === "latest" ? null : Number(value))
              }
            >
              <SelectTrigger aria-label="Select schedule">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="latest">Latest schedule</SelectItem>
                {scheduleOptions.map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    #{item.id} · {algorithmLabel(item.algorithm)} ·{" "}
                    {formatLongDate(item.start_date)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <AlertDialog
              open={dialogOpen}
              onOpenChange={(open) => {
                setDialogOpen(open)
                if (open) setDialogTargetId(selectedId)
              }}
            >
              <AlertDialogTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  disabled={selectedId === null || deleteMutation.isPending}
                  aria-label="Delete schedule"
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete this schedule?</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will permanently remove schedule #{dialogTargetId}, all
                    its shift assignments, and staffing data. This cannot be
                    undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <Button
                    variant="destructive"
                    onClick={() => {
                      if (dialogTargetId !== null)
                        deleteMutation.mutate(dialogTargetId)
                    }}
                    disabled={deleteMutation.isPending}
                  >
                    {deleteMutation.isPending ? "Deleting…" : "Delete"}
                  </Button>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        )}

        {detailQuery.isLoading ? (
          <GridSkeleton />
        ) : noScheduleExists ? (
          <EmptyState
            icon={CalendarDays}
            title="No schedule yet"
            description="Generate your first schedule from the Generate page to see it here."
          />
        ) : detailQuery.isError ? (
          <p role="alert" className="text-sm text-destructive">
            {extractErrorMessage(detailQuery.error, "Could not load schedule.")}
          </p>
        ) : schedule ? (
          <div className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-3">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Summary</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-xs text-muted-foreground">
                      Objective score (F)
                    </p>
                    <p className="text-2xl font-semibold">
                      {schedule.fitness_score?.toFixed(1) ?? "—"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {feasible ? (
                      <Badge variant="success">Feasible</Badge>
                    ) : (
                      <Badge variant="destructive">
                        Hard violations: {hardViolationTotal}
                      </Badge>
                    )}
                    <Badge variant="outline">
                      {algorithmLabel(schedule.algorithm)}
                    </Badge>
                  </div>
                  {!feasible && hardViolationEntries.length > 0 && (
                    <ul className="space-y-1 rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive">
                      {hardViolationEntries.map(([code, count]) => (
                        <li key={code}>
                          <span className="font-medium">
                            {code} ×{count}
                          </span>{" "}
                          <span className="text-destructive/80">
                            ({HARD_CONSTRAINT_LABELS[code as keyof HardViolations]})
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {formatLongDate(schedule.start_date)} —{" "}
                    {formatLongDate(schedule.end_date)}
                  </p>
                </CardContent>
              </Card>

              <Card className="flex flex-col">
                <CardHeader>
                  <CardTitle className="text-base">
                    Scheduled hours per employee
                  </CardTitle>
                </CardHeader>
                <CardContent className="max-h-80 overflow-y-auto">
                  <HoursPerEmployeeChart schedule={schedule} />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    Soft violations by type
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <SoftViolationsChart soft={schedule.soft_violations} />
                </CardContent>
              </Card>
            </div>

            <ScheduleGrid schedule={schedule} />
          </div>
        ) : null}
      </div>
    </TooltipProvider>
  )
}
