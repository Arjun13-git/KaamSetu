import { cn } from "@/lib/cn";
import type { JobStatus, Urgency } from "@/lib/api/types";
import { statusLabel } from "@/lib/status";

export type Tone = "neutral" | "brand" | "ai" | "memory" | "safety" | "ok";

const TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-ink-2 border-line",
  brand: "bg-brand-tint text-brand-strong border-transparent",
  ai: "bg-ai-tint text-ai-strong border-ai-line",
  memory: "bg-memory-paper text-memory-ink border-memory-line",
  safety: "bg-safety-tint text-safety-strong border-safety-line",
  ok: "bg-ok-tint text-ok border-transparent",
};

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium leading-5 whitespace-nowrap",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const DOTS: Record<JobStatus, string> = {
  NEW: "bg-st-new",
  ASSIGNED: "bg-st-assigned",
  SCHEDULED: "bg-st-scheduled",
  ON_THE_WAY: "bg-st-way",
  IN_PROGRESS: "bg-st-progress",
  COMPLETED: "bg-st-done",
  CANCELLED: "bg-st-cancelled",
};

export function StatusDot({ status, className }: { status: JobStatus; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 rounded-full", DOTS[status], className)} />;
}

export function StatusChip({ status }: { status: JobStatus }) {
  return (
    <Badge tone="neutral" className="text-ink">
      <StatusDot status={status} />
      {statusLabel(status)}
    </Badge>
  );
}

export function UrgencyChip({ urgency }: { urgency: Urgency }) {
  if (urgency === "safety_critical") return <Badge tone="safety">Safety-critical</Badge>;
  if (urgency === "high") return <Badge tone="memory">High urgency</Badge>;
  if (urgency === "low") return <Badge tone="neutral">Low urgency</Badge>;
  return null;
}
