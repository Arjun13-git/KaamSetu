import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, CircleCheckBig } from "lucide-react";
import { notFound } from "next/navigation";

import { ServiceMemoryRail } from "@/components/memory/ServiceMemoryRail";
import { JobActions } from "@/components/job/JobActions";
import { AppliancePanel, CustomerPanel, SchedulePanel, TechnicianPanel } from "@/components/job/DetailPanels";
import { LineagePanel } from "@/components/job/LineagePanel";
import { StatusStepper } from "@/components/job/StatusStepper";
import { Badge, StatusChip, UrgencyChip } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SafetyBanner } from "@/components/ui/Safety";
import { ErrorPanel } from "@/components/ui/States";
import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";
import { getTimezone } from "@/lib/config";
import { describeTimePreference, applianceLabel, formatDateTime, formatSlot, localDate, relativeTime, utcToZonedInput } from "@/lib/format";
import { parseExtraction } from "@/lib/extraction";
import { technicianMap, technicianNames } from "@/lib/lookups";
import { nextActions } from "@/lib/status";
import { toMemory, understoodAs } from "@/lib/views";

export const metadata: Metadata = { title: "Job" };

export default async function JobPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const card = await attempt(api.jobCard(id));
  if (!card.ok) {
    if (card.error.status === 404) notFound();
    return <ErrorPanel failure={card.error} title="This job could not be loaded" />;
  }
  const { job, customer, asset, technician } = card.data;
  const tz = getTimezone();
  const now = new Date();

  const [history, request, technicians] = await Promise.all([
    attempt(api.assetHistory(asset.asset_id)),
    job.service_request_id ? attempt(api.serviceRequest(job.service_request_id)) : Promise.resolve(null),
    technicianMap(),
  ]);

  const events = history.ok ? history.data.service_events : card.data.prior_service;
  const label = applianceLabel(asset);
  const memory = toMemory(asset.asset_id, label, events, technicianNames(technicians), tz, now);
  const ownEvent = events.find((event) => event.job_id === job.job_id);
  const extraction = request?.ok ? parseExtraction(request.data.extraction) : null;
  const critical = job.urgency === "safety_critical" || extraction?.safetyConcern === true;
  const open = job.status !== "COMPLETED" && job.status !== "CANCELLED";

  const tomorrowMorning = `${localDate(new Date(now.getTime() + 86_400_000), tz)}T10:00`;
  const defaultSlot = job.preferred_slot ? utcToZonedInput(job.preferred_slot.start, tz) : tomorrowMorning;

  return (
    <>
      <Link href="/" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden />
        Job board
      </Link>

      <header className="mb-5">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <StatusChip status={job.status} />
          <UrgencyChip urgency={job.urgency} />
          <Badge>{job.source === "intake" ? "From intake" : "Entered manually"}</Badge>
          <span className="font-mono text-xs text-ink-3">{job.job_id}</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{job.description}</h1>
        <p className="mt-1 text-ink-2">
          {customer.name} · {label} · created {relativeTime(job.created_at, now)}
        </p>
      </header>

      {critical && open ? <SafetyBanner className="mb-5" /> : null}

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="min-w-0 space-y-5">
          <Card className="p-4 sm:p-5">
            <StatusStepper status={job.status} />
            {open ? (
              <div className="mt-5 border-t border-line pt-4">
                <JobActions
                  jobId={job.job_id}
                  actions={nextActions(job.status, job.technician_id !== null)}
                  technicians={[...technicians.values()].map((t) => ({ id: t.technician_id, name: t.name, skills: t.skills, active: t.active }))}
                  currentTechnicianId={job.technician_id}
                  defaultSlot={defaultSlot}
                  customerName={customer.name}
                />
              </div>
            ) : job.status === "CANCELLED" ? (
              <p className="mt-4 border-t border-line pt-4 text-sm text-ink-2">This job was cancelled. The request and its history are kept.</p>
            ) : null}
          </Card>

          {ownEvent ? (
            <Card className="border-ok/40 bg-ok-tint/40 p-4">
              <p className="flex items-center gap-2 font-semibold text-ok">
                <CircleCheckBig className="size-5" aria-hidden />
                Completed {job.completed_at ? formatDateTime(job.completed_at, tz) : ""}
                {technicians.get(ownEvent.technician_id) ? ` by ${technicians.get(ownEvent.technician_id)?.name}` : ""}
              </p>
              <p className="mt-2 font-medium text-ink">{ownEvent.work_performed}</p>
              {ownEvent.technician_notes ? <p className="mt-1 text-sm text-ink-2">“{ownEvent.technician_notes}”</p> : null}
              <p className="mt-2 text-xs text-ink-3">Recorded as a service event. It now appears in this appliance&rsquo;s Service Memory.</p>
            </Card>
          ) : null}

          {request?.ok ? (
            <LineagePanel
              rawText={request.data.raw_text}
              receivedLabel={formatDateTime(request.data.created_at, tz)}
              understoodAs={understoodAs(extraction, tz, now)}
              extraction={extraction}
              timeLabel={extraction ? describeTimePreference(extraction.data.timePreference, tz, now) : null}
              safety={extraction?.safetyConcern ?? false}
              jobDescription={job.description}
            />
          ) : null}

          <ServiceMemoryRail
            memory={memory}
            current={{ label: open ? "This job" : "This job (now recorded)", text: job.description }}
            recalledLabel={open ? "Recalled for this job" : undefined}
            highlightJobId={job.job_id}
          />
        </div>

        <div className="min-w-0 space-y-5">
          <CustomerPanel customer={customer} />
          <AppliancePanel asset={asset} tz={tz} />
          <TechnicianPanel technician={technician} />
          <SchedulePanel
            scheduled={formatSlot(job.scheduled_slot, tz, now)}
            preferred={formatSlot(job.preferred_slot, tz, now)}
            created={formatDateTime(job.created_at, tz)}
            completed={job.completed_at ? formatDateTime(job.completed_at, tz) : null}
          />
        </div>
      </div>
    </>
  );
}
