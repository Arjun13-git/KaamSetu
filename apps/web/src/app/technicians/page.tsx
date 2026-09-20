import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Suspense } from "react";

import { Badge } from "@/components/ui/Badge";
import { Card, PageHeader } from "@/components/ui/Card";
import { EmptyState, ErrorPanel, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";
import { getTimezone } from "@/lib/config";
import { initials, plural } from "@/lib/format";
import { workloadOf } from "@/lib/technician";

export const metadata: Metadata = { title: "Technicians" };

async function TechnicianList() {
  const [technicians, jobs] = await Promise.all([attempt(api.technicians()), attempt(api.jobs({ limit: 200 }))]);
  if (!technicians.ok) return <ErrorPanel failure={technicians.error} title="Technicians could not be loaded" level={2} />;
  if (technicians.data.length === 0) {
    return (
      <Card>
        <EmptyState title="No technicians yet" />
      </Card>
    );
  }
  const tz = getTimezone();
  const now = new Date();
  const ordered = [...technicians.data].sort((a, b) => Number(b.active) - Number(a.active) || a.name.localeCompare(b.name));
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {ordered.map((tech) => {
        const load = workloadOf((jobs.ok ? jobs.data : []).filter((j) => j.technician_id === tech.technician_id), tz, now);
        return (
          <li key={tech.technician_id}>
            <Link
              href={`/technicians/${tech.technician_id}`}
              className={`flex h-full items-center gap-3 rounded-(--radius-card) border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-pop ${tech.active ? "" : "opacity-70"}`}
            >
              <span className="grid size-11 shrink-0 place-items-center rounded-full bg-brand-tint text-sm font-semibold text-brand-strong">{initials(tech.name)}</span>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 font-semibold">
                  <span className="truncate">{tech.name}</span>
                  {tech.active ? null : <Badge>Inactive</Badge>}
                </p>
                <p className="truncate text-sm text-ink-2">{tech.skills.map((s) => s.replace(/_/g, " ")).join(" · ") || "No skills listed"}</p>
                <p className="mt-1 text-xs text-ink-3">
                  {plural(load.open, "open job")} · {load.today} today
                </p>
              </div>
              <ChevronRight className="size-4 shrink-0 text-ink-3" aria-hidden />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export default function TechniciansPage() {
  return (
    <>
      <PageHeader title="Technicians" subtitle="Open a technician's queue: what is on today, and what they can do next." />
      <Suspense fallback={<Skeleton className="h-48" />}>
        <TechnicianList />
      </Suspense>
    </>
  );
}
