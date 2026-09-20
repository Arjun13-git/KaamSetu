import { Sparkles } from "lucide-react";

import { confidenceBand, sourceLabel, type Source } from "@/lib/extraction";
import { cn } from "@/lib/cn";
import { Badge } from "./Badge";

/** Marks anything the model produced. Blue is reserved for this, and always says what it is. */
export function AiTag({ children = "AI-generated · review", className }: { children?: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full bg-ai-tint px-2 py-0.5 text-xs font-medium text-ai-strong",
        className,
      )}
    >
      <Sparkles className="size-3" aria-hidden />
      {children}
    </span>
  );
}

const BAND_WORD = { high: "High", medium: "Medium", low: "Low" } as const;

export function ConfidenceMeter({ label, value }: { label: string; value: number }) {
  const percent = Math.round(value * 100);
  const band = confidenceBand(value);
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-ink-2">{label}</span>
        <span className="font-medium text-ink">
          {percent}% <span className="font-normal text-ink-3">{BAND_WORD[band]}</span>
        </span>
      </div>
      <div
        role="meter"
        aria-label={`${label} confidence`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-1 h-1.5 overflow-hidden rounded-full bg-ai-tint"
      >
        <div className={cn("h-full rounded-full", band === "low" ? "bg-memory" : "bg-ai")} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

/** A value the customer never gave. Shown as unknown, never as a guess. */
export function UnknownValue({ label = "Not stated" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-ink-3">
      <span aria-hidden className="h-px w-3 bg-line-strong" />
      {label}
    </span>
  );
}

export function ProvenanceChip({ source }: { source: Source }) {
  return (
    <Badge tone={source === "unknown" ? "neutral" : "ai"} className="px-1.5 py-0 text-[11px] leading-4">
      {sourceLabel(source)}
    </Badge>
  );
}
