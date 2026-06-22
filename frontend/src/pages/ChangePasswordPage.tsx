import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation } from "@tanstack/react-query"

import { apiClient, extractErrorMessage } from "@/api/client"
import { PageHeader } from "@/components/PageHeader"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { useToast } from "@/hooks/useToast"

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z
      .string()
      .min(8, "New password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Please confirm your new password"),
  })
  .refine((values) => values.new_password === values.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  })

type PasswordFormValues = z.infer<typeof passwordSchema>

export function ChangePasswordPage() {
  const { toast } = useToast()

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  })

  const mutation = useMutation({
    mutationFn: async (values: PasswordFormValues) => {
      await apiClient.put("/api/auth/password", {
        current_password: values.current_password,
        new_password: values.new_password,
      })
    },
    onSuccess: () => {
      toast({ title: "Password updated successfully." })
      reset()
    },
    onError: (error) => {
      toast({
        variant: "destructive",
        title: "Could not change password",
        description: extractErrorMessage(error),
      })
    },
  })

  const onSubmit = handleSubmit((values) => mutation.mutate(values))

  return (
    <div className="max-w-md">
      <PageHeader
        title="Change Password"
        description="Update the password for your account."
      />
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="current_password">Current password</Label>
              <Input
                id="current_password"
                type="password"
                autoComplete="current-password"
                aria-invalid={Boolean(errors.current_password)}
                aria-describedby={
                  errors.current_password
                    ? "current_password-error"
                    : undefined
                }
                {...register("current_password")}
              />
              {errors.current_password && (
                <p
                  id="current_password-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.current_password.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new_password">New password</Label>
              <Input
                id="new_password"
                type="password"
                autoComplete="new-password"
                aria-invalid={Boolean(errors.new_password)}
                aria-describedby={
                  errors.new_password ? "new_password-error" : undefined
                }
                {...register("new_password")}
              />
              {errors.new_password && (
                <p
                  id="new_password-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.new_password.message}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm_password">Confirm new password</Label>
              <Input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                aria-invalid={Boolean(errors.confirm_password)}
                aria-describedby={
                  errors.confirm_password
                    ? "confirm_password-error"
                    : undefined
                }
                {...register("confirm_password")}
              />
              {errors.confirm_password && (
                <p
                  id="confirm_password-error"
                  role="alert"
                  className="text-sm text-destructive"
                >
                  {errors.confirm_password.message}
                </p>
              )}
            </div>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Spinner label="Saving…" />
              ) : (
                "Update password"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
