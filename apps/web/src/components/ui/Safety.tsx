import { ShieldAlert } from "lucide-react";

import { cn } from "@/lib/cn";

export const SAFETY_NOTICE =
  "The customer reported a possible safety risk. Prioritise this job. KaamSetu records the report as stated; it does not diagnose.";

export function SafetyBanner({ title = "Safety-critical", children, className }: { title?: string; children?: React.ReactNode; className?: string }) {
  return (
    <div
      role="alert"
      className={cn("flex items-start gap-3 rounded-(--radius-card) border border-safety-line bg-safety-tint px-4 py-3", className)}
    >
      <ShieldAlert className="mt-0.5 size-5 shrink-0 text-safety" aria-hidden />
      <div className="min-w-0">
        <p className="font-semibold text-safety-strong">{title}</p>
        <p className="text-sm text-ink-2">{children ?? SAFETY_NOTICE}</p>
      </div>
    </div>
  );
}
