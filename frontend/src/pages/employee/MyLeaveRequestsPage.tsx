import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { CalendarPlus, CalendarRange, Info, Trash2 } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type {
  LeaveRequestResponse,
  LeaveRequestStatus,
} from "@/api/types"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { EmptyState } from "@/components/EmptyState"
import { PageHeader } from "@/components/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
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

const MY_LEAVE_KEY = ["leave-requests", "mine"] as const

const leaveFormSchema = z
  .object({
    start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Choose a start date"),
    end_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Choose an end date"),
    note: z.string().max(1000).optional(),
  })
  .refine((values) => values.start_date <= values.end_date, {
    message: "Start date must not be after end date",
    path: ["end_date"],
  })

type LeaveFormValues = z.infer<typeof leaveFormSchema>

function statusBadge(status: LeaveRequestStatus) {
  switch (status) {
    case "PENDING":
      return <Badge variant="warning">Pending</Badge>
    case "APPROVED":
      return <Badge variant="success">Approved</Badge>
    case "REJECTED":
      return <Badge variant="destructive">Rejected</Badge>
  }
}

function RequestLeaveDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LeaveFormValues>({
    resolver: zodResolver(leaveFormSchema),
    defaultValues: { start_date: "", end_date: "", note: "" },
  })

  const mutation = useMutation({
    mutationFn: async (values: LeaveFormValues) => {
      const { data } = await apiClient.post<LeaveRequestResponse>(
        "/api/leave-requests",
        {
          start_date: values.start_date,
          end_date: values.end_date,
          note: values.note?.trim() || null,
        }
      )
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MY_LEAVE_KEY })
      onOpenChange(false)
      reset()
      toast({ title: "Leave request submitted." })
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not submit request",
        description: extractErrorMessage(error),
      })
    },
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request leave</DialogTitle>
          <DialogDescription>
            Submit a time-off request for your manager to review.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="leave-start">Start date</Label>
              <Input
                id="leave-start"
                type="date"
                aria-invalid={Boolean(errors.start_date)}
                aria-describedby={
                  errors.start_date ? "leave-start-error" : undefined
                }
                {...register("start_date")}
              />
              {errors.start_date && (
                <p
                  id="leave-start-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.start_date.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="leave-end">End date</Label>
              <Input
                id="leave-end"
                type="date"
                aria-invalid={Boolean(errors.end_date)}
                aria-describedby={
                  errors.end_date ? "leave-end-error" : undefined
                }
                {...register("end_date")}
              />
              {errors.end_date && (
                <p
                  id="leave-end-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.end_date.message}
                </p>
              )}
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="leave-note">Note (optional)</Label>
            <Textarea
              id="leave-note"
              maxLength={1000}
              placeholder="Reason or details"
              {...register("note")}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? <Spinner label="Submitting…" /> : "Submit"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function MyLeaveRequestsPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [cancelTarget, setCancelTarget] =
    useState<LeaveRequestResponse | null>(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: MY_LEAVE_KEY,
    queryFn: async () => {
      const { data: requests } = await apiClient.get<LeaveRequestResponse[]>(
        "/api/leave-requests/mine"
      )
      return requests
    },
  })

  const cancelMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/api/leave-requests/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: MY_LEAVE_KEY })
      setCancelTarget(null)
      toast({ title: "Leave request cancelled." })
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Could not cancel request",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  const sorted = [...(data ?? [])].sort((a, b) =>
    b.start_date.localeCompare(a.start_date)
  )

  return (
    <div>
      <PageHeader
        title="Leave Requests"
        description="Submit and track your time-off requests."
        actions={
          <Button onClick={() => setDialogOpen(true)}>
            <CalendarPlus className="h-4 w-4" aria-hidden />
            Request Leave
          </Button>
        }
      />

      <div className="mb-4 flex items-start gap-2 rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
        <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        Submit your request before the manager generates the schedule for this
        period — pending requests are not included in generation.
      </div>

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
              {extractErrorMessage(error, "Could not load your requests.")}
            </p>
          ) : sorted.length === 0 ? (
            <EmptyState
              icon={CalendarRange}
              title="No leave requests"
              description="Submit a request to take time off."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Dates</TableHead>
                  <TableHead>Note</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((request) => (
                  <TableRow key={request.id}>
                    <TableCell className="font-medium">
                      {formatLongDate(request.start_date)} —{" "}
                      {formatLongDate(request.end_date)}
                    </TableCell>
                    <TableCell className="max-w-[16rem] truncate text-muted-foreground">
                      {request.note || "—"}
                    </TableCell>
                    <TableCell>{statusBadge(request.status)}</TableCell>
                    <TableCell className="text-right">
                      {request.status === "PENDING" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setCancelTarget(request)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" aria-hidden />
                          Cancel
                        </Button>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <RequestLeaveDialog open={dialogOpen} onOpenChange={setDialogOpen} />

      <ConfirmDialog
        open={cancelTarget !== null}
        onOpenChange={(open) => {
          if (!open) setCancelTarget(null)
        }}
        title="Cancel leave request?"
        description="This pending request will be withdrawn. You can submit a new one later."
        confirmLabel="Cancel request"
        destructive
        isLoading={cancelMutation.isPending}
        onConfirm={() => {
          if (cancelTarget) cancelMutation.mutate(cancelTarget.id)
        }}
      />
    </div>
  )
}
