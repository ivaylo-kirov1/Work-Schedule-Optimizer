import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { SettingsResponse } from "@/api/types"
import { settingsKey, useSettingsQuery } from "@/api/queries"
import { InfoTooltip } from "@/components/InfoTooltip"
import { PageHeader } from "@/components/PageHeader"
import { WeekdayToggle } from "@/components/WeekdayToggle"
import { Badge } from "@/components/ui/badge"
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

function deriveRegime(offWeekdays: number[]): string {
  const set = new Set(offWeekdays)
  return set.size === 2 && set.has(5) && set.has(6) ? "FIVE_DAY" : "SUMMARIZED"
}

interface SettingsEditorProps {
  initialOffWeekdays: number[]
}


function SettingsEditor({ initialOffWeekdays }: SettingsEditorProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [offWeekdays, setOffWeekdays] = useState<number[]>(initialOffWeekdays)

  const mutation = useMutation({
    mutationFn: async (days: number[]) => {
      const { data } = await apiClient.put<SettingsResponse>("/api/settings", {
        off_weekdays: days,
      })
      return data
    },
    onSuccess: (data) => {
      // new cached array reference changes the editor's key and remounts it
      queryClient.setQueryData(settingsKey, data)
      toast({ title: "Company settings saved." })
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Could not save settings",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  const toggleDay = (day: number) => {
    setOffWeekdays((current) =>
      current.includes(day)
        ? current.filter((value) => value !== day)
        : [...current, day].sort((a, b) => a - b)
    )
  }

  const previewRegime = deriveRegime(offWeekdays)

  return (
    <>
      <WeekdayToggle
        selected={offWeekdays}
        onToggle={toggleDay}
        disabled={mutation.isPending}
      />

      <div className="flex items-center gap-2 rounded-md border bg-muted/30 px-4 py-3">
        <span className="text-sm font-medium">Legal regime:</span>
        <Badge variant="outline">{previewRegime}</Badge>
        <InfoTooltip text="FIVE_DAY when Sat+Sun are both checked. Affects night shift duration cap (Art. 140)." />
      </div>

      <Button
        onClick={() => mutation.mutate(offWeekdays)}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? <Spinner label="Saving…" /> : "Save settings"}
      </Button>
    </>
  )
}

export function SettingsPage() {
  const { data: settings, isLoading, isError, error } = useSettingsQuery()

  return (
    <TooltipProvider delayDuration={150}>
      <div className="max-w-2xl">
        <PageHeader
          title="Company Settings"
          description="Configure the operating regime used by the optimizer."
        />

        <Card>
          <CardHeader>
            <CardTitle>Non-working weekdays</CardTitle>
            <CardDescription>
              Select the days the company is closed every week. Leave all unset
              for 24/7 continuous operation.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {isLoading ? (
              <Skeleton className="h-12 w-full" />
            ) : isError ? (
              <p role="alert" className="text-sm text-destructive">
                {extractErrorMessage(error, "Could not load settings.")}
              </p>
            ) : settings ? (
              <SettingsEditor
                key={JSON.stringify(settings.off_weekdays)}
                initialOffWeekdays={settings.off_weekdays}
              />
            ) : null}
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  )
}
