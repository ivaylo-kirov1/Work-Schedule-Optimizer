import { useMemo, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, Pencil, Trash2, UserPlus, Users } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type {
  CredentialResponse,
  EmployeeResponse,
} from "@/api/types"
import { employeesKey, useEmployeesQuery } from "@/api/queries"
import { EmployeeFormDialog } from "@/components/employees/EmployeeFormDialog"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { CredentialDialog } from "@/components/CredentialDialog"
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

export function EmployeesPage() {
  const { data: employees, isLoading, isError, error } = useEmployeesQuery()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const [showInactive, setShowInactive] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<EmployeeResponse | null>(null)
  const [credential, setCredential] = useState<CredentialResponse | null>(null)
  const [deactivateTarget, setDeactivateTarget] =
    useState<EmployeeResponse | null>(null)
  const [resetTarget, setResetTarget] = useState<EmployeeResponse | null>(null)

  const roles = useMemo(() => {
    const unique = new Set((employees ?? []).map((emp) => emp.role))
    return Array.from(unique).sort()
  }, [employees])

  const visibleEmployees = useMemo(() => {
    const list = employees ?? []
    const filtered = showInactive ? list : list.filter((emp) => emp.is_active)
    return [...filtered].sort((a, b) => a.name.localeCompare(b.name))
  }, [employees, showInactive])

  const deactivateMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/api/employees/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: employeesKey })
      setDeactivateTarget(null)
      toast({ title: "Employee deactivated." })
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Could not deactivate employee",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  const resetMutation = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<CredentialResponse>(
        `/api/employees/${id}/reset-password`
      )
      return data
    },
    onSuccess: (data) => {
      setResetTarget(null)
      setCredential(data)
    },
    onError: (mutationError) => {
      toast({
        variant: "destructive",
        title: "Could not reset password",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  return (
    <div>
      <PageHeader
        title="Employees"
        description="Manage staff records, accounts, and credentials."
        actions={
          <Button
            onClick={() => {
              setEditing(null)
              setDialogOpen(true)
            }}
          >
            <UserPlus className="h-4 w-4" aria-hidden />
            Add Employee
          </Button>
        }
      />

      <datalist id="employee-roles">
        {roles.map((role) => (
          <option key={role} value={role} />
        ))}
      </datalist>

      <div className="mb-4 flex items-center gap-2">
        <Button
          variant={showInactive ? "default" : "outline"}
          size="sm"
          aria-pressed={showInactive}
          onClick={() => setShowInactive((value) => !value)}
        >
          {showInactive ? "Showing all" : "Show deactivated"}
        </Button>
      </div>

      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p role="alert" className="text-sm text-destructive">
              {extractErrorMessage(error, "Could not load employees.")}
            </p>
          ) : visibleEmployees.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No employees yet"
              description="Add your first employee to start building schedules."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Hours / week</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleEmployees.map((employee) => (
                  <TableRow key={employee.id}>
                    <TableCell className="font-medium">
                      {employee.name}
                    </TableCell>
                    <TableCell>{employee.role}</TableCell>
                    <TableCell>{employee.hours_per_week}</TableCell>
                    <TableCell>
                      {employee.is_active ? (
                        <Badge variant="success">Active</Badge>
                      ) : (
                        <Badge variant="secondary">Inactive</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Edit ${employee.name}`}
                          disabled={!employee.is_active}
                          onClick={() => {
                            setEditing(employee)
                            setDialogOpen(true)
                          }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Reset password for ${employee.name}`}
                          disabled={!employee.is_active}
                          onClick={() => setResetTarget(employee)}
                        >
                          <KeyRound className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Deactivate ${employee.name}`}
                          disabled={!employee.is_active}
                          onClick={() => setDeactivateTarget(employee)}
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

      <EmployeeFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        editing={editing}
        onCreated={(cred) => setCredential(cred)}
      />

      <CredentialDialog
        open={credential !== null}
        onOpenChange={(open) => {
          if (!open) setCredential(null)
        }}
        email={credential?.email ?? ""}
        tempPassword={credential?.temp_password ?? ""}
        title="Employee credentials"
      />

      <ConfirmDialog
        open={deactivateTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeactivateTarget(null)
        }}
        title="Deactivate employee?"
        description={`${deactivateTarget?.name ?? "This employee"} will no longer be able to log in or be scheduled. Historical assignments are preserved.`}
        confirmLabel="Deactivate"
        destructive
        isLoading={deactivateMutation.isPending}
        onConfirm={() => {
          if (deactivateTarget) deactivateMutation.mutate(deactivateTarget.id)
        }}
      />

      <ConfirmDialog
        open={resetTarget !== null}
        onOpenChange={(open) => {
          if (!open) setResetTarget(null)
        }}
        title="Reset password?"
        description={`A new one-time password will be generated for ${resetTarget?.name ?? "this employee"}. The current password will stop working.`}
        confirmLabel="Reset password"
        isLoading={resetMutation.isPending}
        onConfirm={() => {
          if (resetTarget) resetMutation.mutate(resetTarget.id)
        }}
      />
    </div>
  )
}
