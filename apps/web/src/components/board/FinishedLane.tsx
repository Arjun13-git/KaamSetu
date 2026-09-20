import { ChevronDown } from "lucide-react";

import { StatusDot } from "@/components/ui/Badge";
import type { BoardView } from "@/lib/board";
import { JobCard } from "./JobCard";

export function FinishedLane({ finished }: { finished: BoardView["finished"] }) {
  const { completed, cancelled } = finished;
  if (completed.length + cancelled.length === 0) return null;
  return (
    <details className="group mt-6 rounded-(--radius-card) border border-line bg-surface shadow-card">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 select-none">
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm font-semibold">
          Finished
          <span className="flex items-center gap-1.5 font-normal text-ink-2">
            <StatusDot status="COMPLETED" /> {completed.length} completed
          </span>
          <span className="flex items-center gap-1.5 font-normal text-ink-2">
            <StatusDot status="CANCELLED" /> {cancelled.length} cancelled
          </span>
        </span>
        <ChevronDown className="size-4 text-ink-3 transition-transform group-open:rotate-180" aria-hidden />
      </summary>
      <div className="grid gap-2 border-t border-line p-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {[...completed, ...cancelled].map((card) => (
          <JobCard key={card.id} card={card} compact showMemory={false} />
        ))}
      </div>
    </details>
  );
}
