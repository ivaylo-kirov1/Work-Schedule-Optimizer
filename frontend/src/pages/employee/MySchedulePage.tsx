import { useQuery } from "@tanstack/react-query"
import { isAxiosError } from "axios"
import { CalendarDays } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { EmployeeScheduleEntry } from "@/api/types"
import { EmptyState } from "@/components/EmptyState"
import { PageHeader } from "@/components/PageHeader"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { formatScheduleDay, formatTime } from "@/lib/format"
import {
  classifyShift,
  shiftCellClasses,
  shiftInitial,
} from "@/lib/shifts"

export function MySchedulePage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["my-schedule"],
    queryFn: async () => {
      const { data: entries } = await apiClient.get<EmployeeScheduleEntry[]>(
        "/api/schedules/latest/me"
      )
      return entries
    },
    retry: (failureCount, queryError) => {
      if (isAxiosError(queryError) && queryError.response?.status === 404) {
        return false
      }
      return failureCount < 2
    },
  })

  const noSchedule = isAxiosError(error) && error.response?.status === 404

  return (
    <TooltipProvider delayDuration={150}>
      <div>
        <PageHeader
          title="My Schedule"
          description="Your assigned shifts for the current planning period."
        />

        {isLoading ? (
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 14 }).map((_, index) => (
              <Skeleton key={index} className="h-20 w-20" />
            ))}
          </div>
        ) : noSchedule ? (
          <EmptyState
            icon={CalendarDays}
            title="No schedule yet"
            description="No schedule has been generated yet. Check back after your manager runs the next generation."
          />
        ) : isError ? (
          <p role="alert" className="text-sm text-destructive">
            {extractErrorMessage(error, "Could not load your schedule.")}
          </p>
        ) : (
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-wrap gap-2">
                {(data ?? []).map((entry) => {
                  const isWorking = entry.shift_type_id != null
                  const category = isWorking
                    ? classifyShift({
                        name: entry.shift_type_name ?? "",
                        start_time: entry.start_time ?? "00:00:00",
                      })
                    : "OFF"
                  const cell = (
                    <div
                      className={`flex h-20 w-20 flex-col items-center justify-center rounded-md border text-center ${shiftCellClasses(category)}`}
                    >
                      <span className="text-xs font-medium">
                        {formatScheduleDay(entry.date)}
                      </span>
                      <span className="text-lg font-semibold">
                        {isWorking
                          ? shiftInitial(category, entry.shift_type_name ?? "")
                          : "—"}
                      </span>
                    </div>
                  )

                  if (!isWorking) {
                    return <div key={entry.date}>{cell}</div>
                  }

                  return (
                    <Tooltip key={entry.date}>
                      <TooltipTrigger asChild>
                        <button type="button" className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md">
                          {cell}
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {entry.shift_type_name}: {formatTime(entry.start_time)} –{" "}
                        {formatTime(entry.end_time)}
                      </TooltipContent>
                    </Tooltip>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </TooltipProvider>
  )
}
