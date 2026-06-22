import { WEEKDAYS } from "@/lib/format"
import { cn } from "@/lib/utils"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface WeekdayToggleProps {
  selected: number[]
  onToggle: (day: number) => void
  disabled?: boolean
  tooltip?: string
}

export function WeekdayToggle({
  selected,
  onToggle,
  disabled = false,
  tooltip,
}: WeekdayToggleProps) {
  const selectedSet = new Set(selected)

  return (
    <div role="group" aria-label="Weekday selection" className="flex flex-wrap gap-2">
      {WEEKDAYS.map((weekday) => {
        const isSelected = selectedSet.has(weekday.value)
        const buttonClassName = cn(
          "h-12 w-14 rounded-md border text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          isSelected
            ? "border-primary bg-primary text-primary-foreground"
            : "border-input bg-background hover:bg-accent"
        )

        if (!tooltip) {
          return (
            <button
              key={weekday.value}
              type="button"
              disabled={disabled}
              aria-pressed={isSelected}
              aria-label={weekday.long}
              onClick={() => onToggle(weekday.value)}
              className={buttonClassName}
            >
              {weekday.short}
            </button>
          )
        }

        return (
          <Tooltip key={weekday.value}>
            <TooltipTrigger asChild>
              <button
                type="button"
                disabled={disabled}
                aria-pressed={isSelected}
                aria-label={weekday.long}
                onClick={() => onToggle(weekday.value)}
                className={buttonClassName}
              >
                {weekday.short}
              </button>
            </TooltipTrigger>
            <TooltipContent>{tooltip}</TooltipContent>
          </Tooltip>
        )
      })}
    </div>
  )
}
