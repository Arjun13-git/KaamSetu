import Link from "next/link";
import { ArrowUpRight, History, Info, MessageSquareQuote, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";
import { initials, plural } from "@/lib/format";
import type { MemoryEventView, MemoryView } from "@/lib/views";

export const MEMORY_DISCLAIMER = "Recorded work, not a diagnosis of the current problem.";

// The rail's axis sits 12px from the left edge of every row, so nodes, line and labels stay aligned.
const AXIS = "left-[11px]";

function Node({ kind, filled }: { kind: "current" | "event"; filled?: boolean }) {
  if (kind === "current") {
    return (
      <span aria-hidden className="absolute top-2.5 left-0 z-10 grid size-6 place-items-center rounded-full border-2 border-ink bg-surface">
        <MessageSquareQuote className="size-3" />
      </span>
    );
  }
  return (
    <span
      aria-hidden
      className={cn(
        "absolute top-[18px] left-1 z-10 size-4 rounded-full border-[3px] border-memory",
        filled ? "bg-memory shadow-[0_0_0_4px_rgb(183_121_31/0.16)]" : "bg-memory-paper",
      )}
    />
  );
}

/** A stretch of the rail with no card on it: the space between two points in time. */
function Gap({ children }: { children: React.ReactNode }) {
  return (
    <li className="relative py-2 pl-10">
      <span aria-hidden className={cn("absolute inset-y-0 w-0.5 bg-memory-line", AXIS)} />
      <span className="inline-flex items-center gap-1.5 rounded-full bg-memory-paper px-2 py-0.5 text-xs font-medium text-memory-ink ring-1 ring-memory-line">
        {children}
      </span>
    </li>
  );
}

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
    <article
      className={cn(
        "rounded-lg border bg-surface px-3.5 py-3 transition-shadow",
        recalled || highlight ? "border-memory shadow-[0_0_0_3px_rgb(183_121_31/0.14)]" : "border-memory-line",
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
          <time dateTime={event.iso} className="text-base font-semibold text-ink">
            {event.dateLabel}
          </time>
          <span className="text-ink-3">{event.agoLabel}</span>
        </p>
        {recalled ? <Badge tone="memory">{recalled}</Badge> : highlight ? <Badge tone="memory">This job</Badge> : null}
      </header>

      <p className="mt-1.5 font-medium text-ink">{event.work}</p>
      {event.notes ? (
        <blockquote className="mt-1.5 border-l-2 border-memory-line pl-3 text-sm text-ink-2">{event.notes}</blockquote>
      ) : null}

      {event.reported.length > 0 || event.parts.length > 0 || event.followUp ? (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
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

      <footer className="mt-2.5 flex items-center justify-between gap-3 border-t border-line pt-2 text-xs">
        <span className="flex min-w-0 items-center gap-1.5 text-ink-2">
          {event.technician ? (
            <>
              <span aria-hidden className="grid size-5 shrink-0 place-items-center rounded-full bg-memory-paper text-[10px] font-semibold text-memory-ink ring-1 ring-memory-line">
                {initials(event.technician)}
              </span>
              <span className="truncate">{event.technician}</span>
            </>
          ) : (
            <span className="text-ink-3">Technician not listed</span>
          )}
        </span>
        <Link
          href={`/jobs/${event.jobId}`}
          className="inline-flex shrink-0 items-center gap-0.5 font-medium text-memory-ink underline-offset-2 hover:underline"
          aria-label={`View the job for the ${event.dateLabel} service`}
        >
          View job
          <ArrowUpRight className="size-3.5" aria-hidden />
        </Link>
      </footer>
    </article>
  );
}

/**
 * The signature element. It shows one appliance's recorded service history as an amber rail and,
 * when given the current request, ties the two together: this request, how long since the last
 * service, then what was done to the same appliance before. Amber means "recorded service" and
 * nothing else in the product. It states what was recorded and never what is wrong now.
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
          <span aria-hidden className="grid size-9 place-items-center rounded-full bg-memory text-white">
            <History className="size-[18px]" />
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
        <ol aria-label="Recorded services, newest first" className="relative">
          {current ? (
            <li className="relative pb-0 pl-10">
              <span aria-hidden className={cn("absolute top-8 -bottom-0 w-0.5 bg-memory-line", AXIS)} />
              <Node kind="current" />
              <div className="rounded-lg border border-dashed border-ink-3 bg-surface/70 px-3.5 py-2.5">
                <p className="text-[11px] font-semibold tracking-wider text-ink-3 uppercase">{current.label}</p>
                <p className="text-sm text-ink">{current.text}</p>
              </div>
            </li>
          ) : null}
          {current && count > 0 && memory.lastServiceAgo ? <Gap>Last serviced {memory.lastServiceAgo}</Gap> : null}

          {count === 0 ? (
            <li className="relative pl-10">
              {current ? <span aria-hidden className={cn("absolute top-0 h-5 w-0.5 bg-memory-line", AXIS)} /> : null}
              <Node kind="event" />
              <p className="mt-2 rounded-lg border border-dashed border-memory-line bg-surface/60 px-3.5 py-3 text-sm text-ink-2">
                No service has been recorded for this appliance yet. The first completed job will start its memory.
              </p>
            </li>
          ) : (
            memory.events.map((event, index) => {
              const last = index === count - 1;
              return (
                <li key={event.id} className="contents">
                  <div className="relative pl-10">
                    {/* the line runs from this node down to the next; it stops at the oldest one */}
                    {last ? null : <span aria-hidden className={cn("absolute top-[26px] -bottom-0 w-0.5 bg-memory-line", AXIS)} />}
                    {index === 0 && current ? null : index === 0 ? null : <span aria-hidden className={cn("absolute top-0 h-[26px] w-0.5 bg-memory-line", AXIS)} />}
                    <Node kind="event" filled={index === 0} />
                    <EventCard event={event} recalled={recalledLabel ?? null} highlight={highlightJobId === event.jobId} />
                  </div>
                  {event.earlierBy && !last ? <Gap>{event.earlierBy} earlier</Gap> : null}
                </li>
              );
            })
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
