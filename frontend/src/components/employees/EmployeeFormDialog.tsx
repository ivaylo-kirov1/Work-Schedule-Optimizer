import { useForm, type Resolver } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiClient, extractErrorMessage } from "@/api/client"
import type {
  CredentialResponse,
  EmployeeResponse,
} from "@/api/types"
import { employeesKey } from "@/api/queries"
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

const baseEmployeeSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  role: z.string().min(1, "Role is required").max(50),
  hours_per_week: z
    .number({ message: "Enter the weekly hours" })
    .int("Hours must be a whole number")
    .gt(0, "Hours must be greater than 0")
    .lte(168, "Hours cannot exceed 168"),
})

const createEmployeeSchema = baseEmployeeSchema.extend({
  email: z
    .string()
    .min(5)
    .max(150)
    .regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, "Enter a valid email"),
})

const editEmployeeSchema = baseEmployeeSchema.extend({
  email: z.string().optional().default(""),
})

type EmployeeFormValues = z.infer<typeof createEmployeeSchema>

interface EmployeeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editing: EmployeeResponse | null
  onCreated: (credential: CredentialResponse) => void
}

export function EmployeeFormDialog({
  open,
  onOpenChange,
  editing,
  onCreated,
}: EmployeeDialogProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const isEdit = editing !== null

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EmployeeFormValues>({
    resolver: zodResolver(isEdit ? editEmployeeSchema : createEmployeeSchema) as Resolver<EmployeeFormValues>,
    values: {
      name: editing?.name ?? "",
      role: editing?.role ?? "",
      hours_per_week: editing?.hours_per_week ?? 40,
      email: "",
    },
  })

  const mutation = useMutation({
    mutationFn: async (values: EmployeeFormValues) => {
      if (isEdit && editing) {
        const { data } = await apiClient.put<EmployeeResponse>(
          `/api/employees/${editing.id}`,
          {
            name: values.name,
            role: values.role,
            hours_per_week: values.hours_per_week,
          }
        )
        return { kind: "update" as const, data }
      }
      const { data } = await apiClient.post<CredentialResponse>(
        "/api/employees",
        values
      )
      return { kind: "create" as const, data }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: employeesKey })
      onOpenChange(false)
      reset()
      if (result.kind === "create") {
        onCreated(result.data)
      } else {
        toast({ title: "Employee updated." })
      }
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: isEdit ? "Update failed" : "Could not create employee",
        description: extractErrorMessage(error),
      })
    },
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit employee" : "Add employee"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update this employee's details. The email address cannot be changed."
              : "A one-time password is generated automatically after creation."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="emp-name">Name</Label>
            <Input
              id="emp-name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? "emp-name-error" : undefined}
              {...register("name")}
            />
            {errors.name && (
              <p
                id="emp-name-error"
                role="alert"
                className="text-sm text-destructive"
              >
                {errors.name.message}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="emp-role">Role</Label>
            <Input
              id="emp-role"
              list="employee-roles"
              aria-invalid={Boolean(errors.role)}
              aria-describedby={errors.role ? "emp-role-error" : undefined}
              {...register("role")}
            />
            {errors.role && (
              <p
                id="emp-role-error"
                role="alert"
                className="text-sm text-destructive"
              >
                {errors.role.message}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="emp-hours">Hours per week</Label>
            <Input
              id="emp-hours"
              type="number"
              min={1}
              max={168}
              aria-invalid={Boolean(errors.hours_per_week)}
              aria-describedby={
                errors.hours_per_week ? "emp-hours-error" : undefined
              }
              {...register("hours_per_week", { valueAsNumber: true })}
            />
            {errors.hours_per_week && (
              <p
                id="emp-hours-error"
                role="alert"
                className="text-sm text-destructive"
              >
                {errors.hours_per_week.message}
              </p>
            )}
          </div>
          {!isEdit && (
            <div className="space-y-1.5">
              <Label htmlFor="emp-email">Email</Label>
              <Input
                id="emp-email"
                type="email"
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? "emp-email-error" : undefined}
                {...register("email")}
              />
              {errors.email && (
                <p
                  id="emp-email-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.email.message}
                </p>
              )}
            </div>
          )}
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
              ) : isEdit ? (
                "Save changes"
              ) : (
                "Create employee"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
