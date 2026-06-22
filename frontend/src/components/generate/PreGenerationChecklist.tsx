import { useState } from "react"
import { ChevronDown, ChevronRight } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"

interface ChecklistItem {
  id: string
  label: string
}

const CHECKLIST: ChecklistItem[] = [
  { id: "leave", label: "All relevant leave requests have been approved" },
  { id: "closures", label: "Company-specific non-working dates have been added" },
  { id: "norms", label: "Monthly norms are adjusted for any company closures" },
  { id: "staffing", label: "Staffing values are set for all shift types" },
]

export function PreGenerationChecklist() {
  const [open, setOpen] = useState(false)
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  return (
    <Card>
      <button
        type="button"
        className="flex w-full flex-col space-y-1.5 p-6 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <CardTitle className="flex items-center gap-2 text-base">
          {open ? (
            <ChevronDown className="h-4 w-4" aria-hidden />
          ) : (
            <ChevronRight className="h-4 w-4" aria-hidden />
          )}
          Pre-generation checklist
        </CardTitle>
        <CardDescription>
          Optional reminders — none of these block generation.
        </CardDescription>
      </button>
      {open && (
        <CardContent className="space-y-2">
          {CHECKLIST.map((item) => (
            <label
              key={item.id}
              className="flex items-center gap-3 text-sm"
              htmlFor={`checklist-${item.id}`}
            >
              <Checkbox
                id={`checklist-${item.id}`}
                checked={checked[item.id] ?? false}
                onCheckedChange={(value) =>
                  setChecked((current) => ({
                    ...current,
                    [item.id]: value === true,
                  }))
                }
              />
              {item.label}
            </label>
          ))}
        </CardContent>
      )}
    </Card>
  )
}
