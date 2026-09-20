import { Check, Lock } from "lucide-react";

import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";

export type StepState = "done" | "current" | "locked";

/** One decision in the review: a person confirms it before the next one opens. */
export function ReviewStep({
  index,
  title,
  state,
  action,
  children,
}: {
  index: number;
  title: string;
  state: StepState;
  action?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <Card className={cn("p-4 sm:p-5", state === "current" && "border-brand/50", state === "locked" && "bg-surface/60 shadow-none")}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-3 font-semibold">
          <span
            className={cn(
              "grid size-7 shrink-0 place-items-center rounded-full border-2 text-sm",
              state === "done" && "border-brand bg-brand text-white",
              state === "current" && "border-brand text-brand",
              state === "locked" && "border-line-strong text-ink-3",
            )}
          >
            {state === "done" ? <Check className="size-4" aria-hidden /> : state === "locked" ? <Lock className="size-3.5" aria-hidden /> : index}
          </span>
          <span className={cn(state === "locked" && "text-ink-3")}>{title}</span>
        </h2>
        {action}
      </div>
      {state === "locked" ? null : <div className="mt-4">{children}</div>}
    </Card>
  );
}
