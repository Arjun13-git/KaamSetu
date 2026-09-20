import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Phone } from "lucide-react";
import { notFound } from "next/navigation";

import { JobRow } from "@/components/customers/JobRow";
import { TechnicianJobCard } from "@/components/technicians/TechnicianJobCard";
import { WorkloadTiles } from "@/components/technicians/WorkloadTiles";
import { Badge } from "@/components/ui/Badge";
import { Card, SectionLabel } from "@/components/ui/Card";
import { EmptyState, ErrorPanel } from "@/components/ui/States";
import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";
import { getTimezone } from "@/lib/config";
import { formatDate, formatPhone, initials, relativeTime } from "@/lib/format";
import { ENTITY_ID } from "@/lib/review";
import { buildQueue } from "@/lib/technician";

export const metadata: Metadata = { title: "Technician queue" };

export default async function TechnicianPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!ENTITY_ID.test(id)) notFound();
  const [technicians, jobs] = await Promise.all([attempt(api.technicians()), attempt(api.jobs({ technicianId: id, limit: 200 }))]);
  if (!technicians.ok) return <ErrorPanel failure={technicians.error} title="This technician could not be loaded" />;
  const tech = technicians.data.find((t) => t.technician_id === id);
  if (!tech) notFound();
  if (!jobs.ok) return <ErrorPanel failure={jobs.error} title="The queue could not be loaded" />;

  const tz = getTimezone();
  const now = new Date();
  const queue = buildQueue(jobs.data, tz, now);
  const names = new Map(technicians.data.map((t) => [t.technician_id, t.name]));

  // One call per open job returns the customer, the appliance and its recorded service together.
  const open = [...queue.today, ...queue.later];
  const cards = new Map((await Promise.all(open.map((job) => attempt(api.jobCard(job.job_id))))).flatMap((r) => (r.ok ? [[r.data.job.job_id, r.data] as const] : [])));
  const section = (title: string, list: typeof open, empty: string) => (
    <section aria-label={title} className="space-y-3">
      <SectionLabel className="px-1">
        {title} · {list.length}
      </SectionLabel>
      {list.length === 0 ? (
        <Card>
          <EmptyState title={empty} />
        </Card>
      ) : (
        list.map((job) => {
          const card = cards.get(job.job_id);
          return card ? (
            <TechnicianJobCard key={job.job_id} card={card} technicianNames={names} tz={tz} now={now} />
          ) : (
            <JobRow key={job.job_id} job={job} technicianName={tech.name} ago={`created ${relativeTime(job.created_at, now)}`} />
          );
        })
      )}
    </section>
  );

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/technicians" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden />
        Technicians
      </Link>

      <Card className="mb-6 p-4 sm:p-5">
        <div className="flex items-center gap-4">
          <span className="grid size-14 shrink-0 place-items-center rounded-full bg-brand-tint text-lg font-semibold text-brand-strong">{initials(tech.name)}</span>
          <div className="min-w-0">
            <h1 className="flex flex-wrap items-center gap-2 text-2xl font-semibold tracking-tight">
              {tech.name}
              {tech.active ? null : <Badge>Inactive</Badge>}
            </h1>
            <p className="mt-0.5 text-sm text-ink-2">
              {formatDate(now.toISOString(), tz)} · {queue.workload.today} on today · {queue.workload.open} open
            </p>
            {tech.phone ? (
              <a href={`tel:${tech.phone}`} className="mt-1 inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
                <Phone className="size-3.5" aria-hidden />
                {formatPhone(tech.phone)}
              </a>
            ) : null}
          </div>
        </div>
        {tech.skills.length > 0 ? (
          <p className="mt-3 flex flex-wrap gap-1.5">
            {tech.skills.map((skill) => (
              <Badge key={skill}>{skill.replace(/_/g, " ")}</Badge>
            ))}
          </p>
        ) : null}
        <div className="mt-4">
          <WorkloadTiles workload={queue.workload} />
        </div>
      </Card>

      <div className="space-y-8">
        {section("Today", queue.today, "Nothing on for today")}
        {queue.later.length > 0 ? section("Later", queue.later, "") : null}
        {queue.recentlyCompleted.length > 0 ? (
          <section aria-label="Recently completed" className="space-y-2">
            <SectionLabel className="px-1">Recently completed</SectionLabel>
            {queue.recentlyCompleted.map((job) => (
              <JobRow key={job.job_id} job={job} technicianName={tech.name} ago={`completed ${relativeTime(job.completed_at ?? job.updated_at, now)}`} />
            ))}
          </section>
        ) : null}
      </div>
    </div>
  );
}
