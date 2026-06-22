import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Info } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { PreferencesResponse } from "@/api/types"
import { PageHeader } from "@/components/PageHeader"
import { WeekdayToggle } from "@/components/WeekdayToggle"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useToast } from "@/hooks/useToast"
import { useAuth } from "@/hooks/useAuth"

const PREFER_DAY_OFF_TOOLTIP =
  "Prefer this day off every week. The algorithm will try to respect this but cannot always guarantee it."

interface PreferencesEditorProps {
  employeeId: number
  preferencesKey: readonly unknown[]
  initialDays: number[]
}


function PreferencesEditor({
  employeeId,
  preferencesKey,
  initialDays,
}: PreferencesEditorProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [selected, setSelected] = useState<number[]>(initialDays)

  const mutation = useMutation({
    mutationFn: async (days: number[]) => {
      const { data: saved } = await apiClient.put<PreferencesResponse>(
        `/api/employees/${employeeId}/preferences`,
        { days }
      )
      return saved
    },
    onSuccess: (saved) => {
      // new cached array reference changes the editor's key and remounts it.
      queryClient.setQueryData(preferencesKey, saved)
      toast({ title: "Preferences saved." })
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Could not save preferences",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  const toggleDay = (day: number) => {
    setSelected((current) =>
      current.includes(day)
        ? current.filter((value) => value !== day)
        : [...current, day].sort((a, b) => a - b)
    )
  }

  return (
    <>
      <WeekdayToggle
        selected={selected}
        onToggle={toggleDay}
        disabled={mutation.isPending}
        tooltip={PREFER_DAY_OFF_TOOLTIP}
      />
      <Button
        onClick={() => mutation.mutate(selected)}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? <Spinner label="Saving…" /> : "Save preferences"}
      </Button>
    </>
  )
}

export function PreferencesPage() {
  const { user } = useAuth()
  const employeeId = user?.employeeId ?? null

  const preferencesKey = ["preferences", employeeId] as const

  const { data, isLoading, isError, error } = useQuery({
    queryKey: preferencesKey,
    enabled: employeeId != null,
    queryFn: async () => {
      const { data: prefs } = await apiClient.get<PreferencesResponse>(
        `/api/employees/${employeeId}/preferences`
      )
      return prefs
    },
  })

  return (
    <TooltipProvider delayDuration={150}>
      <div className="max-w-2xl">
        <PageHeader
          title="My Preferences"
          description="Tell the optimizer which days you would prefer to have off."
        />

        <div className="mb-4 flex items-start gap-2 rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          These preferences are taken into account the next time the manager
          generates a schedule. They do not affect the current schedule.
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Preferred days off</CardTitle>
            <CardDescription>
              Select the weekdays you would like to avoid working.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {employeeId == null ? (
              <p role="alert" className="text-sm text-destructive">
                Your account is not linked to an employee record.
              </p>
            ) : isLoading ? (
              <Skeleton className="h-12 w-full" />
            ) : isError ? (
              <p role="alert" className="text-sm text-destructive">
                {extractErrorMessage(error, "Could not load preferences.")}
              </p>
            ) : data ? (
              <PreferencesEditor
                key={JSON.stringify(data.days)}
                employeeId={employeeId}
                preferencesKey={preferencesKey}
                initialDays={data.days}
              />
            ) : null}
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  )
}
