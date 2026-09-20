import Link from "next/link";
import { ChevronRight, MessageSquareWarning, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import type { BoardView } from "@/lib/board";
import { JobCard } from "./JobCard";

/**
 * What a dispatcher must not miss: dangerous jobs, and requests waiting on a person's decision.
 * Safety is marked by a crimson header band, an icon and words (never colour alone) and stays a
 * quiet white panel below it, so it is unmistakable without flooding the page.
 */
export function NeedsAttention({ attention }: { attention: BoardView["attention"] }) {
  const { safety, review } = attention;
  if (safety.length === 0 && review.length === 0) return null;
  return (
    <section aria-label="Needs attention" className="mb-6 grid items-start gap-4 lg:grid-cols-2">
      {safety.length > 0 ? (
        <div className="overflow-hidden rounded-(--radius-card) border border-safety-line bg-surface shadow-card">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-b border-safety-line bg-safety-tint px-4 py-2.5">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-safety-strong">
              <ShieldAlert className="size-4" aria-hidden />
              Safety-critical · {safety.length}
            </h2>
            <p className="text-xs text-ink-2">A possible safety risk was reported. KaamSetu records it; it does not diagnose.</p>
          </div>
          <div className="grid gap-2 p-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {safety.map((card) => (
              <JobCard key={card.id} card={card} compact />
            ))}
          </div>
        </div>
      ) : null}
      {review.length > 0 ? (
        <div className="overflow-hidden rounded-(--radius-card) border border-line bg-surface shadow-card">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-b border-line bg-sunken/70 px-4 py-2.5">
            <h2 className="flex items-center gap-2 text-sm font-semibold">
              <MessageSquareWarning className="size-4 text-ink-2" aria-hidden />
              Waiting for review · {review.length}
            </h2>
            <p className="text-xs text-ink-2">KaamSetu would not make these into jobs without a person.</p>
          </div>
          <ul className="space-y-0.5 p-2">
            {review.map((row) => (
              <li key={row.id}>
                <Link href={`/requests/${row.id}`} className="flex items-center justify-between gap-3 rounded-lg px-2 py-2 hover:bg-sunken">
                  <div className="min-w-0">
                    <p className="line-clamp-1 text-sm">“{row.text}”</p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink-3">
                      <Badge>{row.reason}</Badge>
                      {row.seeded ? <Badge>Seeded example</Badge> : null}
                      {row.ageLabel}
                    </p>
                  </div>
                  <ChevronRight className="size-4 shrink-0 text-ink-3" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
