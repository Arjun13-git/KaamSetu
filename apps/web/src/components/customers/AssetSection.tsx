import { UnknownValue } from "@/components/ui/Ai";
import { ServiceMemoryRail } from "@/components/memory/ServiceMemoryRail";
import { Badge } from "@/components/ui/Badge";
import type { Asset, Job } from "@/lib/api/types";
import { applianceLabel, formatDate, relativeTime } from "@/lib/format";
import type { MemoryView } from "@/lib/views";
import { JobRow } from "./JobRow";

/** One appliance: what is known about it, its open work, and its recorded service history. */
export function AssetSection({
  asset,
  memory,
  openJobs,
  technicianNames,
  tz,
  now,
}: {
  asset: Asset;
  memory: MemoryView;
  openJobs: Job[];
  technicianNames: Map<string, string>;
  tz: string;
  now: Date;
}) {
  return (
    <section
      id={asset.asset_id}
      aria-label={applianceLabel(asset)}
      className="scroll-mt-20 rounded-(--radius-card) target:ring-2 target:ring-memory/50 target:ring-offset-4 target:ring-offset-canvas"
    >
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
        <h2 className="text-lg font-semibold tracking-tight">{applianceLabel(asset)}</h2>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2">
          <span>{asset.location ?? <UnknownValue label="Location not recorded" />}</span>
          <span>Model: {asset.model ?? <UnknownValue label="not recorded" />}</span>
          {asset.warranty_until ? <span>Warranty until {formatDate(`${asset.warranty_until}T12:00:00Z`, tz)}</span> : null}
        </p>
        {openJobs.length > 0 ? <Badge tone="brand">{openJobs.length} open</Badge> : null}
      </div>

      {openJobs.length > 0 ? (
        <div className="mb-3 space-y-2">
          {openJobs.map((job) => (
            <JobRow
              key={job.job_id}
              job={job}
              technicianName={job.technician_id ? (technicianNames.get(job.technician_id) ?? "Technician") : null}
              ago={`created ${relativeTime(job.created_at, now)}`}
            />
          ))}
        </div>
      ) : null}

      <ServiceMemoryRail memory={memory} />
    </section>
  );
}
