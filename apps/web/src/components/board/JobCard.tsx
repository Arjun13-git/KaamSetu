import Link from "next/link";
import { Clock, History, ShieldAlert, UserRound } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import { plural } from "@/lib/format";
import type { BoardCard } from "@/lib/board";

export function TechnicianTag({ technician }: { technician: BoardCard["technician"] }) {
  if (!technician) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-dashed border-line-strong px-2 py-0.5 text-xs text-ink-3">
        <UserRound className="size-3" aria-hidden />
        Unassigned
      </span>
    );
  }
  return (
    <span className="inline-flex min-w-0 items-center gap-1.5 text-xs text-ink-2">
      <span className="grid size-5 shrink-0 place-items-center rounded-full bg-brand-tint text-[10px] font-semibold text-brand-strong">
        {technician.initials}
      </span>
      <span className="truncate">{technician.name}</span>
    </span>
  );
}

export function JobCard({ card, compact, showMemory = true }: { card: BoardCard; compact?: boolean; showMemory?: boolean }) {
  const critical = card.urgency === "safety_critical";
  const flagged = critical || card.urgency === "high";
  const age = <span className="shrink-0 text-xs text-ink-3">{card.ageLabel}</span>;
  return (
    <Link
      href={card.href}
      className={cn(
        "group relative block overflow-hidden rounded-lg border bg-surface p-3 shadow-card transition-shadow hover:shadow-pop",
        critical ? "border-safety-line pl-4" : "border-line",
      )}
    >
      {critical ? <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-safety" /> : null}
      {flagged ? (
        <div className="mb-1.5 flex items-center justify-between gap-2">
          {critical ? (
            <Badge tone="safety">
              <ShieldAlert className="size-3" aria-hidden />
              Safety-critical
            </Badge>
          ) : (
            <Badge className="border-ink-3 text-ink">High urgency</Badge>
          )}
          {age}
        </div>
      ) : null}
      <div className="flex items-start justify-between gap-2">
        <p className={cn("min-w-0 font-medium text-ink", compact ? "line-clamp-1" : "line-clamp-2")}>{card.description}</p>
        {flagged ? null : age}
      </div>
      <p className="mt-0.5 truncate text-sm text-ink-2">
        {card.customerName}
        {card.appliance ? <span className="text-ink-3"> · {card.appliance}</span> : null}
      </p>
      {showMemory && card.pastServices > 0 ? (
        <Badge tone="memory" className="mt-2">
          <History className="size-3" aria-hidden />
          {plural(card.pastServices, "past service")}
        </Badge>
      ) : null}
      <div className="mt-2.5 space-y-1.5 border-t border-line pt-2">
        {card.slot ? (
          <p className="flex items-center gap-1.5 text-xs text-ink-2" title={card.slot.kind === "scheduled" ? "Scheduled" : "Customer's preferred time"}>
            <Clock className="size-3 shrink-0 text-ink-3" aria-hidden />
            <span className="truncate">
              {card.slot.kind === "preferred" ? "Prefers " : ""}
              {card.slot.label}
            </span>
          </p>
        ) : null}
        <TechnicianTag technician={card.technician} />
      </div>
    </Link>
  );
}
