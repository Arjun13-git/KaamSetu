import { StatusDot } from "@/components/ui/Badge";
import { statusLabel } from "@/lib/status";
import type { BoardCard } from "@/lib/board";
import type { JobStatus } from "@/lib/api/types";
import { JobCard } from "./JobCard";

export function StatusColumn({ status, cards }: { status: JobStatus; cards: BoardCard[] }) {
  return (
    <section aria-label={statusLabel(status)} className="flex min-h-40 min-w-0 flex-col rounded-(--radius-card) bg-sunken/70 p-2">
      <header className="flex items-center justify-between px-2 py-1.5">
        <h2 className="flex items-center gap-2 text-sm font-semibold">
          <StatusDot status={status} />
          {statusLabel(status)}
        </h2>
        <span className="rounded-full bg-surface px-2 text-xs font-medium text-ink-2">{cards.length}</span>
      </header>
      <div className="flex flex-1 flex-col gap-2">
        {cards.length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-ink-3">Nothing here</p>
        ) : (
          cards.map((card) => <JobCard key={card.id} card={card} />)
        )}
      </div>
    </section>
  );
}
