import { useMemo, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil, Plus, Sliders, Trash2 } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { ShiftTypeResponse } from "@/api/types"
import { shiftTypesKey, useShiftTypesQuery } from "@/api/queries"
import { ShiftFormDialog } from "@/components/shift-types/ShiftFormDialog"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { EmptyState } from "@/components/EmptyState"
import { PageHeader } from "@/components/PageHeader"
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
import { formatTime } from "@/lib/format"
import { shiftDurationHours } from "@/lib/shifts"

export function ShiftTypesPage() {
  const { data: shiftTypes, isLoading, isError, error } = useShiftTypesQuery()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<ShiftTypeResponse | null>(null)
  const [retireTarget, setRetireTarget] = useState<ShiftTypeResponse | null>(
    null
  )
  const [showRetired, setShowRetired] = useState(false)

  const { active, retired } = useMemo(() => {
    const list = shiftTypes ?? []
    return {
      active: list.filter((shift) => shift.is_active),
      retired: list.filter((shift) => !shift.is_active),
    }
  }, [shiftTypes])

  const retireMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/api/shift-types/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: shiftTypesKey })
      setRetireTarget(null)
      toast({ title: "Shift type retired." })
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Could not retire shift type",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  const renderRow = (shift: ShiftTypeResponse, isActiveRow: boolean) => (
    <TableRow key={shift.id}>
      <TableCell className="font-medium">{shift.name}</TableCell>
      <TableCell>{formatTime(shift.start_time)}</TableCell>
      <TableCell>{formatTime(shift.end_time)}</TableCell>
      <TableCell>
        {shiftDurationHours(shift.start_time, shift.end_time).toFixed(1)} h
      </TableCell>
      {isActiveRow && (
        <TableCell className="text-right">
          <div className="flex justify-end gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Edit ${shift.name}`}
              onClick={() => {
                setEditing(shift)
                setDialogOpen(true)
              }}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label={`Retire ${shift.name}`}
              onClick={() => setRetireTarget(shift)}
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </TableCell>
      )}
    </TableRow>
  )

  return (
    <div>
      <PageHeader
        title="Shift Types"
        description="Define the shifts the optimizer can assign."
        actions={
          <Button
            onClick={() => {
              setEditing(null)
              setDialogOpen(true)
            }}
          >
            <Plus className="h-4 w-4" aria-hidden />
            Add Shift Type
          </Button>
        }
      />

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p role="alert" className="text-sm text-destructive">
              {extractErrorMessage(error, "Could not load shift types.")}
            </p>
          ) : active.length === 0 ? (
            <EmptyState
              icon={Sliders}
              title="No active shift types"
              description="Add at least one shift type before generating a schedule."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Start</TableHead>
                  <TableHead>End</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {active.map((shift) => renderRow(shift, true))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {retired.length > 0 && (
        <div className="mt-6">
          <Button
            variant="outline"
            size="sm"
            aria-expanded={showRetired}
            onClick={() => setShowRetired((value) => !value)}
          >
            {showRetired ? "Hide" : "Show"} retired shift types (
            {retired.length})
          </Button>
          {showRetired && (
            <Card className="mt-3">
              <CardContent className="pt-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Start</TableHead>
                      <TableHead>End</TableHead>
                      <TableHead>Duration</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {retired.map((shift) => renderRow(shift, false))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <ShiftFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editing={editing}
      />

      <ConfirmDialog
        open={retireTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRetireTarget(null)
        }}
        title="Retire shift type?"
        description={`${retireTarget?.name ?? "This shift type"} will no longer be used in new schedules. Existing schedules keep their assignments.`}
        confirmLabel="Retire"
        destructive
        isLoading={retireMutation.isPending}
        onConfirm={() => {
          if (retireTarget) retireMutation.mutate(retireTarget.id)
        }}
      />
    </div>
  )
}
