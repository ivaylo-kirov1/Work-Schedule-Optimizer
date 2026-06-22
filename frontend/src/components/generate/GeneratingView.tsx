import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"

import { apiClient } from "@/api/client"
import type { TaskStatusResponse } from "@/api/types"
import { formatElapsed } from "@/lib/format"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface GeneratingViewProps {
  taskId: string
  startedAt: number
  onCompleted: () => void
  onFailed: (message: string) => void
  onCancel: () => void
}

export function GeneratingView({ taskId, startedAt, onCompleted, onFailed, onCancel }: GeneratingViewProps) {
  const [elapsed, setElapsed] = useState(() =>
    Math.floor((Date.now() - startedAt) / 1000)
  )
  const [cancelling, setCancelling] = useState(false)

  useEffect(() => {
    const interval = window.setInterval(() => setElapsed((s) => s + 1), 1000)
    return () => window.clearInterval(interval)
  }, [])

  const { data } = useQuery({
    queryKey: ["task-status", taskId],
    queryFn: async () => {
      const { data: status } = await apiClient.get<TaskStatusResponse>(
        `/api/tasks/${taskId}/status`
      )
      return status
    },
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === "COMPLETED" || status === "FAILED") return false
      if (query.state.status === "error") return false
      return 3000
    },
  })

  useEffect(() => {
    if (!data) return
    if (data.status === "COMPLETED") {
      onCompleted()
    } else if (data.status === "FAILED") {
      onFailed(data.error ?? "Schedule generation failed.")
    }
  }, [data, onCompleted, onFailed])

  async function handleCancel() {
    setCancelling(true)
    try {
      await apiClient.delete(`/api/tasks/${taskId}`)
    } catch {
      // task may have already finished — let onCancel clean up
    }
    onCancel()
  }

  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-6 py-16">
        <Loader2 className="h-10 w-10 animate-spin text-primary" aria-hidden />
        <div className="text-center" role="status" aria-live="polite">
          <p className="text-lg font-medium">Generating schedule…</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Elapsed: {formatElapsed(elapsed)}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Status: {data?.status ?? "PENDING"}
          </p>
        </div>
        <Button variant="outline" onClick={handleCancel} disabled={cancelling}>
          {cancelling ? "Cancelling…" : "Cancel"}
        </Button>
      </CardContent>
    </Card>
  )
}
