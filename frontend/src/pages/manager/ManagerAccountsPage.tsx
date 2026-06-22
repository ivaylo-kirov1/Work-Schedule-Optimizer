import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { KeyRound, ShieldCheck, Trash2, UserPlus } from "lucide-react"

import { apiClient, extractErrorMessage } from "@/api/client"
import type {
  ManagerCredentialResponse,
  ManagerResponse,
} from "@/api/types"
import { managersKey, useManagersQuery } from "@/api/queries"
import { ManagerFormDialog } from "@/components/managers/ManagerFormDialog"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { CredentialDialog } from "@/components/CredentialDialog"
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
import { useAuth } from "@/hooks/useAuth"
import { formatDateTime } from "@/lib/format"

export function ManagerAccountsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: managers, isLoading, isError, error } = useManagersQuery()

  const [dialogOpen, setDialogOpen] = useState(false)
  const [credential, setCredential] =
    useState<ManagerCredentialResponse | null>(null)
  const [resetTarget, setResetTarget] = useState<ManagerResponse | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ManagerResponse | null>(null)

  const resetMutation = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<ManagerCredentialResponse>(
        `/api/managers/${id}/reset-password`
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

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(`/api/managers/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: managersKey })
      setDeleteTarget(null)
      toast({ title: "Manager removed." })
    },
    onError: (mutationError) => {
      setDeleteTarget(null)
      toast({
        variant: "destructive",
        title: "Could not remove manager",
        description: extractErrorMessage(mutationError),
      })
    },
  })

  return (
    <div>
      <PageHeader
        title="Manager Accounts"
        description="Manage administrator accounts for the system."
        actions={
          <Button onClick={() => setDialogOpen(true)}>
            <UserPlus className="h-4 w-4" aria-hidden />
            Add Manager
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
              {extractErrorMessage(error, "Could not load managers.")}
            </p>
          ) : !managers || managers.length === 0 ? (
            <EmptyState
              icon={ShieldCheck}
              title="No managers"
              description="Add a manager account to share administration duties."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {managers.map((manager) => {
                  const isSelf = user?.email === manager.email
                  return (
                    <TableRow key={manager.id}>
                      <TableCell className="font-medium">
                        {manager.email}
                        {isSelf && (
                          <span className="ml-2 text-xs text-muted-foreground">
                            (you)
                          </span>
                        )}
                      </TableCell>
                      <TableCell>{formatDateTime(manager.created_at)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Reset password for ${manager.email}`}
                            onClick={() => setResetTarget(manager)}
                          >
                            <KeyRound className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            aria-label={`Delete ${manager.email}`}
                            disabled={manager.id === user?.id}
                            title={
                              manager.id === user?.id
                                ? "You cannot delete your own account"
                                : undefined
                            }
                            onClick={() => setDeleteTarget(manager)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ManagerFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreated={(cred) => setCredential(cred)}
      />

      <CredentialDialog
        open={credential !== null}
        onOpenChange={(open) => {
          if (!open) setCredential(null)
        }}
        email={credential?.email ?? ""}
        tempPassword={credential?.temp_password ?? ""}
        title="Manager credentials"
      />

      <ConfirmDialog
        open={resetTarget !== null}
        onOpenChange={(open) => {
          if (!open) setResetTarget(null)
        }}
        title="Reset password?"
        description={`A new one-time password will be generated for ${resetTarget?.email ?? "this manager"}. The current password will stop working.`}
        confirmLabel="Reset password"
        isLoading={resetMutation.isPending}
        onConfirm={() => {
          if (resetTarget) resetMutation.mutate(resetTarget.id)
        }}
      />

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        title="Delete manager?"
        description={`${deleteTarget?.email ?? "This manager"} will permanently lose access. You cannot delete the last remaining manager.`}
        confirmLabel="Delete"
        destructive
        isLoading={deleteMutation.isPending}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id)
        }}
      />
    </div>
  )
}
