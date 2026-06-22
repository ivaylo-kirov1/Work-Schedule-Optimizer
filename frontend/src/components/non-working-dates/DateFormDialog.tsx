import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"

import { apiClient, extractErrorMessage } from "@/api/client"
import type { NonWorkingDateResponse } from "@/api/types"
import { nonWorkingDatesKey } from "@/api/queries"
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

const dateFormSchema = z.object({
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Choose a date"),
  note: z.string().max(100).optional(),
})

type DateFormValues = z.infer<typeof dateFormSchema>

interface DateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editing: NonWorkingDateResponse | null
}

export function DateFormDialog({ open, onOpenChange, editing }: DateDialogProps) {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const isEdit = editing !== null

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<DateFormValues>({
    resolver: zodResolver(dateFormSchema),
    values: {
      date: editing?.date ?? "",
      note: editing?.note ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: async (values: DateFormValues) => {
      const body = { date: values.date, note: values.note?.trim() || null }
      if (isEdit && editing) {
        await apiClient.put(`/api/non-working-dates/${editing.id}`, body)
      } else {
        await apiClient.post("/api/non-working-dates", body)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: nonWorkingDatesKey })
      onOpenChange(false)
      reset()
      toast({ title: isEdit ? "Date updated." : "Non-working date added." })
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: isEdit ? "Update failed" : "Could not add date",
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
            {isEdit ? "Edit non-working date" : "Add non-working date"}
          </DialogTitle>
          <DialogDescription>
            A company-specific closure day (e.g. a public holiday).
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="space-y-1.5">
            <Label htmlFor="nwd-date">Date</Label>
            <Input
              id="nwd-date"
              type="date"
              aria-invalid={Boolean(errors.date)}
              aria-describedby={errors.date ? "nwd-date-error" : undefined}
              {...register("date")}
            />
            {errors.date && (
              <p
                id="nwd-date-error"
                role="alert"
                className="text-sm text-destructive"
              >
                {errors.date.message}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nwd-note">Note (optional)</Label>
            <Input
              id="nwd-note"
              maxLength={100}
              placeholder="e.g. Public holiday"
              aria-invalid={Boolean(errors.note)}
              aria-describedby={errors.note ? "nwd-note-error" : undefined}
              {...register("note")}
            />
            {errors.note && (
              <p
                id="nwd-note-error"
                role="alert"
                className="text-sm text-destructive"
              >
                {errors.note.message}
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
              ) : isEdit ? (
                "Save changes"
              ) : (
                "Add date"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
