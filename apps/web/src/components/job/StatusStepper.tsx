import { Check } from "lucide-react";

import { cn } from "@/lib/cn";
import type { JobStatus } from "@/lib/api/types";
import { PROGRESS_STEPS, statusLabel } from "@/lib/status";

export function StatusStepper({ status }: { status: JobStatus }) {
  const cancelled = status === "CANCELLED";
  const current = PROGRESS_STEPS.indexOf(status);
  return (
    <ol aria-label="Job progress" className="flex items-start">
      {PROGRESS_STEPS.map((step, index) => {
        const done = !cancelled && index < current;
        const active = !cancelled && index === current;
        const finished = active && status === "COMPLETED";
        return (
          <li key={step} className="relative flex min-w-0 flex-1 flex-col items-center gap-1.5 text-center" aria-current={active ? "step" : undefined}>
            {index > 0 ? (
              <span aria-hidden className={cn("absolute top-3 right-1/2 h-0.5 w-full", done || active ? "bg-brand" : "bg-line-strong")} />
            ) : null}
            <span
              className={cn(
                "relative z-10 grid size-6 place-items-center rounded-full border-2 text-[11px] font-semibold",
                done || finished ? "border-brand bg-brand text-white" : active ? "border-brand bg-surface text-brand" : "border-line-strong bg-surface text-ink-3",
                cancelled && "border-line-strong bg-sunken",
              )}
            >
              {done || finished ? <Check className="size-3.5" aria-hidden /> : index + 1}
            </span>
            <span className={cn("text-[11px] leading-tight sm:text-xs", active ? "font-semibold text-ink" : "text-ink-3")}>{statusLabel(step)}</span>
          </li>
        );
      })}
    </ol>
  );
}
