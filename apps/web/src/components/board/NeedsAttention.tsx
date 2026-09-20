import { ChevronRight, MessageSquareWarning, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card, SectionLabel } from "@/components/ui/Card";
import type { BoardView } from "@/lib/board";
import { JobCard } from "./JobCard";

/** What a dispatcher must not miss: dangerous jobs, and requests waiting on a person's decision. */
export function NeedsAttention({ attention }: { attention: BoardView["attention"] }) {
  const { safety, review } = attention;
  if (safety.length === 0 && review.length === 0) return null;
  return (
    <section aria-label="Needs attention" className="mb-6 grid gap-4 lg:grid-cols-2">
      {safety.length > 0 ? (
        <div className="rounded-(--radius-card) border border-safety-line bg-safety-tint p-3">
          <div className="mb-2 flex items-center gap-2 px-1">
            <ShieldAlert className="size-4 text-safety" aria-hidden />
            <SectionLabel className="text-safety-strong">Safety-critical · {safety.length}</SectionLabel>
          </div>
          <p className="mb-3 px-1 text-sm text-ink-2">
            Customers reported a possible safety risk. KaamSetu records the report; it does not diagnose.
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {safety.map((card) => (
              <JobCard key={card.id} card={card} compact />
            ))}
          </div>
        </div>
      ) : null}
      {review.length > 0 ? (
        <Card className="p-3">
          <div className="mb-2 flex items-center gap-2 px-1">
            <MessageSquareWarning className="size-4 text-ink-2" aria-hidden />
            <SectionLabel>Waiting for review · {review.length}</SectionLabel>
          </div>
          <p className="mb-3 px-1 text-sm text-ink-2">Requests KaamSetu would not turn into a job without a person.</p>
          <ul className="divide-y divide-line">
            {review.map((row) => {
              const inner = (
                <>
                  <div className="min-w-0">
                    <p className="line-clamp-1 text-sm">“{row.text}”</p>
                    <p className="mt-0.5 flex items-center gap-2 text-xs text-ink-3">
                      <Badge>{row.reason}</Badge>
                      {row.ageLabel}
                    </p>
                  </div>
                  <ChevronRight className="size-4 shrink-0 text-ink-3" aria-hidden />
                </>
              );
              return (
                <li key={row.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
                  {inner}
                </li>
              );
            })}
          </ul>
        </Card>
      ) : null}
    </section>
  );
}
