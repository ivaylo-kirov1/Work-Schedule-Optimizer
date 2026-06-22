import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { addMonths, isAfter, isBefore, parseISO } from "date-fns"
import { CalendarOff, Pencil, Plus, Trash2 } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { NonWorkingDateResponse } from "@/api/types"
import {
  nonWorkingDatesKey,
  useNonWorkingDatesQuery,
} from "@/api/queries"
import { DateFormDialog } from "@/components/non-working-dates/DateFormDialog"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { EmptyState } from "@/components/EmptyState"
import { PageHeader } from "@/components/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useToast } from "@/hooks/useToast"
import { formatLongDate } from "@/lib/format"

function isWithinNextThreeMonths(isoDate: string): boolean {
  const date = parseISO(isoDate)
  const now = new Date()
  const threeMonths = addMonths(now, 3)
  return !isBefore(date, now) && !isAfter(date, threeMonths)
}

export function NonWorkingDatesPage() {
  const { data: dates, isLoading, isError, error } = useNonWorkingDatesQuery()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<NonWorkingDateResponse | null>(null)
  const [deleteTarget, setDeleteTarget] =
    useState<NonWorkingDateResponse | null>(null)

  const sortedDates = [...(dates ?? [])].sort((a, b) =>
    a.date.localeCompare(b.date)
  )

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/api/non-working-dates/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nonWorkingDatesKey })
      setDeleteTarget(null)
      toast({ title: "Non-working date removed." })
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Could not remove date",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  return (
    <div>
      <PageHeader
        title="Non-Working Dates"
        description="Company-specific closure days excluded from scheduling."
        actions={
          <Button
            onClick={() => {
              setEditing(null)
              setDialogOpen(true)
            }}
          >
            <Plus className="h-4 w-4" aria-hidden />
            Add Date
          </Button>
        }
      />

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p role="alert" className="text-sm text-destructive">
              {extractErrorMessage(error, "Could not load dates.")}
            </p>
          ) : sortedDates.length === 0 ? (
            <EmptyState
              icon={CalendarOff}
              title="No non-working dates"
              description="Add closure days such as public holidays so the optimizer skips them."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Note</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedDates.map((entry) => (
                  <TableRow
                    key={entry.id}
                    className={
                      isWithinNextThreeMonths(entry.date)
                        ? "bg-amber-50"
                        : undefined
                    }
                  >
                    <TableCell className="font-medium">
                      <span className="flex items-center gap-2">
                        {formatLongDate(entry.date)}
                        {isWithinNextThreeMonths(entry.date) && (
                          <Badge variant="warning">Upcoming</Badge>
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {entry.note || "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit ${entry.date}`}
                          onClick={() => {
                            setEditing(entry)
                            setDialogOpen(true)
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Delete ${entry.date}`}
                          onClick={() => setDeleteTarget(entry)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <DateFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editing={editing}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        title="Remove non-working date?"
        description={`${deleteTarget ? formatLongDate(deleteTarget.date) : "This date"} will become a normal working day again.`}
        confirmLabel="Remove"
        destructive
        isLoading={deleteMutation.isPending}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id)
        }}
      />
    </div>
  )
}
