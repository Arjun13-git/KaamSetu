import Link from "next/link";
import { Clock, History, MapPin, Phone, ShieldAlert, Wrench } from "lucide-react";

import { JobActions } from "@/components/job/JobActions";
import { ServiceMemoryRail } from "@/components/memory/ServiceMemoryRail";
import { Badge, StatusChip, UrgencyChip } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import type { JobCard } from "@/lib/api/types";
import { applianceLabel, formatPhone, formatSlot, plural } from "@/lib/format";
import { cn } from "@/lib/cn";
import { nextActions } from "@/lib/status";
import { toMemory } from "@/lib/views";

/** Everything a technician needs at the door, and only the moves they can make. */
export function TechnicianJobCard({
  card,
  technicianNames,
  tz,
  now,
}: {
  card: JobCard;
  technicianNames: Map<string, string>;
  tz: string;
  now: Date;
}) {
  const { job, customer, asset } = card;
  const critical = job.urgency === "safety_critical";
  const label = applianceLabel(asset);
  const memory = toMemory(asset.asset_id, label, card.prior_service, technicianNames, tz, now);
  const latest = memory.events[0];
  const scheduled = formatSlot(job.scheduled_slot, tz, now);
  const preferred = formatSlot(job.preferred_slot, tz, now);
  // A technician moves work forward and completes it; assigning and cancelling are the dispatcher's.
  const actions = nextActions(job.status, true).filter((a) => a.kind === "transition" || a.kind === "complete");
  const phone = formatPhone(customer.phone);

  return (
    <Card className={cn("relative overflow-hidden p-4", critical && "border-safety-line")}>
      {critical ? <span aria-hidden className="absolute inset-y-0 left-0 w-1 bg-safety" /> : null}
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip status={job.status} />
        <UrgencyChip urgency={job.urgency} />
      </div>
      <h3 className="mt-2 text-lg leading-snug font-semibold tracking-tight">{job.description}</h3>

      {critical ? (
        <p className="mt-2 flex items-start gap-2 rounded-lg bg-safety-tint px-3 py-2 text-sm text-safety-strong">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
          The customer reported a possible safety risk. Take care on arrival. KaamSetu records the report; it does not diagnose.
        </p>
      ) : null}

      <ul className="mt-3 space-y-2 text-sm">
        <li className="flex items-start gap-2.5">
          <Wrench className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
          <span>
            <span className="font-medium">{label}</span>
            {asset.location ? <span className="text-ink-2"> · {asset.location}</span> : null}
          </span>
        </li>
        <li className="flex items-start gap-2.5">
          <MapPin className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
          <span>
            <Link href={`/customers/${customer.customer_id}`} className="font-medium hover:underline">
              {customer.name}
            </Link>
            {customer.address ? <span className="block text-ink-2">{customer.address}</span> : null}
          </span>
        </li>
        <li className="flex items-center gap-2.5">
          <Clock className="size-4 shrink-0 text-ink-3" aria-hidden />
          <span>{scheduled ? `Scheduled ${scheduled}` : preferred ? `Customer prefers ${preferred}` : "No time set"}</span>
        </li>
      </ul>

      {phone && customer.phone ? (
        <a
          href={`tel:${customer.phone}`}
          className="mt-3 inline-flex h-11 items-center gap-2 rounded-lg border border-line-strong bg-surface px-4 text-sm font-medium hover:bg-sunken"
        >
          <Phone className="size-4" aria-hidden />
          Call {customer.name.split(" ")[0]} · {phone}
        </a>
      ) : null}

      <div className="mt-4 rounded-lg border border-memory-line bg-memory-paper px-3.5 py-3">
        <p className="flex flex-wrap items-center gap-2 text-[11px] font-semibold tracking-wider text-memory-ink uppercase">
          <History className="size-3.5" aria-hidden />
          Service memory
          <Badge tone="memory">{plural(memory.events.length, "recorded service")}</Badge>
        </p>
        {latest ? (
          <p className="mt-1.5 text-sm">
            <span className="font-medium">{latest.dateLabel}</span> <span className="text-ink-3">({latest.agoLabel})</span>: {latest.work}
            {latest.notes ? <span className="block text-ink-2">“{latest.notes}”</span> : null}
          </p>
        ) : (
          <p className="mt-1.5 text-sm text-ink-2">Nothing recorded for this appliance yet.</p>
        )}
        <p className="mt-1.5 text-xs text-memory-ink">Recorded work, not a diagnosis of the current problem.</p>
        {memory.events.length > 1 ? (
          <details className="mt-2">
            <summary className="flex min-h-10 cursor-pointer items-center text-sm font-medium text-memory-ink select-none">Full history</summary>
            <div className="mt-2">
              <ServiceMemoryRail memory={memory} />
            </div>
          </details>
        ) : null}
      </div>

      {actions.length > 0 ? (
        <div className="mt-4">
          <JobActions jobId={job.job_id} actions={actions} technicians={[]} currentTechnicianId={job.technician_id} defaultSlot="" customerName={customer.name} large />
        </div>
      ) : null}
      <Link href={`/jobs/${job.job_id}`} className="mt-3 inline-block text-sm font-medium text-brand-strong hover:underline">
        Full job details
      </Link>
    </Card>
  );
}
