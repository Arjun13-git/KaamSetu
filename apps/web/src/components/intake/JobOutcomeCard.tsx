import Link from "next/link";
import { ArrowRight, BriefcaseBusiness, Clock, UserRoundCheck } from "lucide-react";

import { Badge, StatusChip, UrgencyChip } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { IntakeView } from "@/lib/views";

/** The end of the chain: a job exists, or the reason a person still has to decide something. */
export function JobOutcomeCard({ view }: { view: IntakeView }) {
  if (view.job) {
    const job = view.job;
    const critical = job.urgency === "safety_critical";
    return (
      <Card className={cn("p-4", critical ? "border-safety-line bg-safety-tint/40" : "border-brand/40")}>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={critical ? "safety" : "brand"}>
            <BriefcaseBusiness className="size-3" aria-hidden />
            Job created
          </Badge>
          <StatusChip status={job.status} />
          <UrgencyChip urgency={job.urgency} />
          <Badge>From intake</Badge>
        </div>
        <p className="mt-3 text-lg font-semibold tracking-tight">{job.description}</p>
        <ul className="mt-2 space-y-1 text-sm text-ink-2">
          <li className="flex items-center gap-2">
            <Clock className="size-4 text-ink-3" aria-hidden />
            {job.slotLabel ? `Customer prefers ${job.slotLabel}` : "No preferred time given"}
          </li>
          <li className="flex items-center gap-2">
            <UserRoundCheck className="size-4 text-ink-3" aria-hidden />
            No technician yet. Assign one from the job.
          </li>
        </ul>
        <Link href={job.href} className={buttonClass("primary", "md", "mt-4")}>
          Open job
          <ArrowRight className="size-4" aria-hidden />
        </Link>
      </Card>
    );
  }

  if (view.outcome === "manual_entry_required") {
    return (
      <Card className="p-4">
        <Badge>No job yet</Badge>
        <p className="mt-2 font-medium">The AI could not read this message.</p>
        <p className="mt-1 text-sm text-ink-2">
          The request is saved exactly as it was written, so nothing is lost. A person can create the job by hand.
        </p>
        {view.failureReason ? <p className="mt-2 font-mono text-xs text-ink-3">{view.failureReason}</p> : null}
      </Card>
    );
  }

  return (
    <Card className="border-ink-3 p-4">
      <Badge>Needs review · no job created</Badge>
      <p className="mt-2 font-medium">A person needs to confirm before a job is created.</p>
      <ul className="mt-2 space-y-1.5 text-sm text-ink-2">
        {view.reviewReasons.map((reason) => (
          <li key={reason} className="flex items-start gap-2">
            <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-ink-3" />
            {reason}
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-ink-3">
        KaamSetu does not guess. The message and what was understood are saved as request{" "}
        <span className="font-mono">{view.serviceRequestId.slice(-8)}</span>.
      </p>
    </Card>
  );
}
