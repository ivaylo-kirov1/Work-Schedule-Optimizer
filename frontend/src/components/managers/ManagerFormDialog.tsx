import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { ManagerCredentialResponse } from "@/api/types"
import { managersKey } from "@/api/queries"
import { Button } from "@/components/ui/button"
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
import { Spinner } from "@/components/ui/spinner"
import { useToast } from "@/hooks/useToast"

const managerFormSchema = z.object({
  email: z
    .string()
    .min(5)
    .max(150)
    .regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, "Enter a valid email"),
})

type ManagerFormValues = z.infer<typeof managerFormSchema>

interface ManagerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (credential: ManagerCredentialResponse) => void
}

export function ManagerFormDialog({
  open,
  onOpenChange,
  onCreated,
}: ManagerDialogProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ManagerFormValues>({
    resolver: zodResolver(managerFormSchema),
    defaultValues: { email: "" },
  })

  const mutation = useMutation({
    mutationFn: async (values: ManagerFormValues) => {
      const { data } = await apiClient.post<ManagerCredentialResponse>(
        "/api/managers",
        values
      )
      return data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: managersKey })
      onOpenChange(false)
      reset()
      onCreated(data)
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not create manager",
        description: extractErrorMessage(error),
      })
    },
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add manager</DialogTitle>
          <DialogDescription>
            A one-time password is generated automatically after creation.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="manager-email">Email</Label>
            <Input
              id="manager-email"
              type="email"
              aria-invalid={Boolean(errors.email)}
              aria-describedby={
                errors.email ? "manager-email-error" : undefined
              }
              {...register("email")}
            />
            {errors.email && (
              <p
                id="manager-email-error"
                role="alert"
                className="text-sm text-destructive"
              >
                {errors.email.message}
              </p>
            )}
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
              {mutation.isPending ? (
                <Spinner label="Saving…" />
              ) : (
                "Create manager"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
