import { useMemo, useState } from "react"
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { Check, CalendarRange, X } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type {
  LeaveRequestResponse,
  LeaveRequestStatus,
} from "@/api/types"
import { useEmployeesQuery } from "@/api/queries"
import { EmptyState } from "@/components/EmptyState"
import { PageHeader } from "@/components/PageHeader"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
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

type FilterValue = "ALL" | LeaveRequestStatus

const LEAVE_REQUESTS_KEY = "leave-requests"

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

export function LeaveRequestsPage() {
  const [filter, setFilter] = useState<FilterValue>("ALL")
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: employees } = useEmployeesQuery()
  const employeeNames = useMemo(() => {
    const map = new Map<number, string>()
    for (const emp of employees ?? []) map.set(emp.id, emp.name)
    return map
  }, [employees])

  const {
    data: requests,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: [LEAVE_REQUESTS_KEY, "manager", filter],
    queryFn: async () => {
      const params = filter === "ALL" ? undefined : { status: filter }
      const { data } = await apiClient.get<LeaveRequestResponse[]>(
        "/api/leave-requests",
        { params }
      )
      return data
    },
  })

  const decisionMutation = useMutation({
    mutationFn: async ({
      id,
      decision,
    }: {
      id: number
      decision: "approve" | "reject"
    }) => {
      const { data } = await apiClient.patch<LeaveRequestResponse>(
        `/api/leave-requests/${id}/${decision}`
      )
      return data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: [LEAVE_REQUESTS_KEY, "manager"],
      })
      toast({
        title:
          variables.decision === "approve"
            ? "Leave request approved."
            : "Leave request rejected.",
      })
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Action failed",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  return (
    <div>
      <PageHeader
        title="Leave Requests"
        description="Review and respond to employee time-off requests."
      />

      <Tabs
        value={filter}
        onValueChange={(value) => setFilter(value as FilterValue)}
        className="mb-4"
      >
        <TabsList>
          <TabsTrigger value="ALL">All</TabsTrigger>
          <TabsTrigger value="PENDING">Pending</TabsTrigger>
          <TabsTrigger value="APPROVED">Approved</TabsTrigger>
          <TabsTrigger value="REJECTED">Rejected</TabsTrigger>
        </TabsList>
      </Tabs>

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
              {extractErrorMessage(error, "Could not load leave requests.")}
            </p>
          ) : !requests || requests.length === 0 ? (
            <EmptyState
              icon={CalendarRange}
              title="No leave requests"
              description="There are no requests matching this filter."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Dates</TableHead>
                  <TableHead>Note</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.map((request) => {
                  const employeeName =
                    employeeNames.get(request.employee_id) ??
                    `Employee #${request.employee_id}`
                  const dateRange = `${request.start_date} to ${request.end_date}`
                  return (
                    <TableRow key={request.id}>
                      <TableCell className="font-medium">
                        {employeeName}
                      </TableCell>
                      <TableCell>
                        {formatLongDate(request.start_date)} —{" "}
                        {formatLongDate(request.end_date)}
                      </TableCell>
                      <TableCell className="max-w-[16rem] truncate text-muted-foreground">
                        {request.note || "—"}
                      </TableCell>
                      <TableCell>{statusBadge(request.status)}</TableCell>
                      <TableCell className="text-right">
                        {request.status === "PENDING" ? (
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              aria-label={`Approve leave request from ${employeeName}, ${dateRange}`}
                              disabled={decisionMutation.isPending}
                              onClick={() =>
                                decisionMutation.mutate({
                                  id: request.id,
                                  decision: "approve",
                                })
                              }
                            >
                              <Check className="h-4 w-4" aria-hidden />
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              aria-label={`Reject leave request from ${employeeName}, ${dateRange}`}
                              disabled={decisionMutation.isPending}
                              onClick={() =>
                                decisionMutation.mutate({
                                  id: request.id,
                                  decision: "reject",
                                })
                              }
                            >
                              <X className="h-4 w-4" aria-hidden />
                              Reject
                            </Button>
                          </div>
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            —
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
