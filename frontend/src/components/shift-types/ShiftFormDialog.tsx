import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { ShiftTypeResponse } from "@/api/types"
import { shiftTypesKey } from "@/api/queries"
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

const shiftFormSchema = z.object({
  name: z.string().min(1, "Name is required").max(50),
  start_time: z
    .string()
    .regex(/^([01]\d|2[0-3]):[0-5]\d$/, "Use HH:MM (00:00–23:59)"),
  end_time: z
    .string()
    .regex(/^([01]\d|2[0-3]):[0-5]\d$/, "Use HH:MM (00:00–23:59)"),
})

type ShiftFormValues = z.infer<typeof shiftFormSchema>

function toTimeField(apiTime: string): string {
  return apiTime.slice(0, 5)
}

function toApiTime(field: string): string {
  return `${field}:00`
}

interface ShiftDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editing: ShiftTypeResponse | null
}

export function ShiftFormDialog({ open, onOpenChange, editing }: ShiftDialogProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const isEdit = editing !== null

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ShiftFormValues>({
    resolver: zodResolver(shiftFormSchema),
    values: {
      name: editing?.name ?? "",
      start_time: editing ? toTimeField(editing.start_time) : "08:00",
      end_time: editing ? toTimeField(editing.end_time) : "16:00",
    },
  })

  const mutation = useMutation({
    mutationFn: async (values: ShiftFormValues) => {
      const body = {
        name: values.name,
        start_time: toApiTime(values.start_time),
        end_time: toApiTime(values.end_time),
      }
      if (isEdit && editing) {
        await apiClient.put(`/api/shift-types/${editing.id}`, body)
      } else {
        await apiClient.post("/api/shift-types", body)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: shiftTypesKey })
      onOpenChange(false)
      reset()
      toast({ title: isEdit ? "Shift type updated." : "Shift type created." })
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: isEdit ? "Update failed" : "Could not create shift type",
        description: extractErrorMessage(error),
      })
    },
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit shift type" : "Add shift type"}
          </DialogTitle>
          <DialogDescription>
            Use 24-hour HH:MM times. A shift may cross midnight (e.g. 00:00 end).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="shift-name">Name</Label>
            <Input
              id="shift-name"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? "shift-name-error" : undefined}
              {...register("name")}
            />
            {errors.name && (
              <p
                id="shift-name-error"
                role="alert"
                className="text-sm text-destructive"
              >
                {errors.name.message}
              </p>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="shift-start">Start time</Label>
              <Input
                id="shift-start"
                type="time"
                aria-invalid={Boolean(errors.start_time)}
                aria-describedby={
                  errors.start_time ? "shift-start-error" : undefined
                }
                {...register("start_time")}
              />
              {errors.start_time && (
                <p
                  id="shift-start-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.start_time.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="shift-end">End time</Label>
              <Input
                id="shift-end"
                type="time"
                aria-invalid={Boolean(errors.end_time)}
                aria-describedby={
                  errors.end_time ? "shift-end-error" : undefined
                }
                {...register("end_time")}
              />
              {errors.end_time && (
                <p
                  id="shift-end-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.end_time.message}
                </p>
              )}
            </div>
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
              ) : isEdit ? (
                "Save changes"
              ) : (
                "Create shift type"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
