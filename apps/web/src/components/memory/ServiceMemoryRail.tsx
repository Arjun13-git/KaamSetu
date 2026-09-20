import Link from "next/link";
import { History, Info, MessageSquareQuote, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import { plural } from "@/lib/format";
import type { MemoryEventView, MemoryView } from "@/lib/views";

export const MEMORY_DISCLAIMER = "Recorded work, not a diagnosis of the current problem.";

function EventCard({
  event,
  recalled,
  highlight,
}: {
  event: MemoryEventView;
  recalled: string | null;
  highlight: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border bg-surface px-3.5 py-3",
        recalled || highlight ? "border-memory shadow-[0_0_0_3px_rgb(183_121_31/0.14)]" : "border-memory-line",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <p className="text-sm">
          <span className="font-semibold text-ink">{event.dateLabel}</span>
          <span className="text-ink-3"> · {event.agoLabel}</span>
          {event.technician ? <span className="text-ink-3"> · {event.technician}</span> : null}
        </p>
        {recalled ? <Badge tone="memory">{recalled}</Badge> : null}
        {highlight && !recalled ? <Badge tone="memory">This job</Badge> : null}
      </div>
      <p className="mt-1.5 font-medium text-ink">{event.work}</p>
      {event.notes ? <p className="mt-1 text-sm text-ink-2">“{event.notes}”</p> : null}
      {event.reported.length > 0 || event.parts.length > 0 || event.followUp ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {event.reported.map((symptom) => (
            <Badge key={`s-${symptom}`}>Reported: {symptom}</Badge>
          ))}
          {event.parts.map((part) => (
            <Badge key={`p-${part}`}>
              <Wrench className="size-3" aria-hidden />
              {part}
            </Badge>
          ))}
          {event.followUp ? <Badge tone="memory">Follow-up flagged</Badge> : null}
        </div>
      ) : null}
      <Link href={`/jobs/${event.jobId}`} className="mt-2 inline-block text-xs font-medium text-memory-ink underline-offset-2 hover:underline">
        View that job
      </Link>
    </div>
  );
}

/**
 * The signature element. It shows the appliance's recorded service history as an amber rail and,
 * when given the current request, ties the two together: this request, then what was done to the
 * same appliance before. Amber means "recorded service" and nothing else in the product.
 */
export function ServiceMemoryRail({
  memory,
  current,
  recalledLabel,
  highlightJobId,
  className,
}: {
  memory: MemoryView;
  /** The request or job being looked at now, shown at the head of the rail. */
  current?: { label: string; text: string };
  /** Tag put on each event when the memory is being recalled for a request. */
  recalledLabel?: string;
  highlightJobId?: string;
  className?: string;
}) {
  const count = memory.events.length;
  return (
    <section
      aria-label={`Service memory for ${memory.assetLabel}`}
      className={cn("overflow-hidden rounded-(--radius-card) border border-memory-line bg-memory-paper", className)}
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-memory-line px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="grid size-9 place-items-center rounded-full bg-memory text-white">
            <History className="size-[18px]" aria-hidden />
          </span>
          <div>
            <p className="text-[11px] font-semibold tracking-wider text-memory-ink uppercase">Service memory</p>
            <p className="leading-tight font-semibold text-ink">{memory.assetLabel}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="memory">{plural(count, "recorded service")}</Badge>
          {memory.lastServiceAgo ? <Badge tone="memory">Last serviced {memory.lastServiceAgo}</Badge> : null}
        </div>
      </header>

      <div className="px-4 py-4">
        <ol className="relative space-y-3.5">
          {/* the rail: one line from this request down through every recorded service */}
          <span aria-hidden className="absolute top-3 bottom-3 left-[11px] w-0.5 rounded bg-memory-line" />
          {current ? (
            <li className="relative pl-9">
              <span aria-hidden className="absolute top-3 left-0 grid size-6 place-items-center rounded-full border-2 border-ink bg-surface">
                <MessageSquareQuote className="size-3" />
              </span>
              <div className="rounded-lg border border-dashed border-ink-3 bg-surface/70 px-3.5 py-2.5">
                <p className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">{current.label}</p>
                <p className="text-sm text-ink">{current.text}</p>
              </div>
            </li>
          ) : null}
          {count === 0 ? (
            <li className="relative pl-9">
              <span aria-hidden className="absolute top-3 left-[7px] size-2.5 rounded-full bg-memory-line" />
              <p className="rounded-lg border border-dashed border-memory-line bg-surface/60 px-3.5 py-3 text-sm text-ink-2">
                No service has been recorded for this appliance yet. The first completed job will start its memory.
              </p>
            </li>
          ) : (
            memory.events.map((event) => (
              <li key={event.id} className="relative pl-9">
                <span aria-hidden className="absolute top-4 left-[5px] size-3.5 rounded-full border-[3px] border-memory bg-surface" />
                <EventCard
                  event={event}
                  recalled={recalledLabel ?? null}
                  highlight={highlightJobId === event.jobId}
                />
              </li>
            ))
          )}
        </ol>
      </div>

      <footer className="flex items-center gap-2 border-t border-memory-line px-4 py-2.5 text-xs text-memory-ink">
        <Info className="size-3.5 shrink-0" aria-hidden />
        {MEMORY_DISCLAIMER}
      </footer>
    </section>
  );
}
