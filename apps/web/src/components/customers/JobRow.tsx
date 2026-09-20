import Link from "next/link";
import { ChevronRight } from "lucide-react";

import { StatusChip, UrgencyChip } from "@/components/ui/Badge";
import type { Job } from "@/lib/api/types";

export function JobRow({ job, technicianName, ago }: { job: Job; technicianName: string | null; ago: string }) {
  return (
    <Link href={`/jobs/${job.job_id}`} className="flex items-center justify-between gap-3 rounded-lg border border-line bg-surface px-3 py-2.5 hover:bg-sunken">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{job.description}</p>
        <p className="mt-0.5 text-xs text-ink-3">
          {technicianName ?? "Unassigned"} · {ago}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <UrgencyChip urgency={job.urgency} />
        <StatusChip status={job.status} />
        <ChevronRight className="size-4 text-ink-3" aria-hidden />
      </div>
    </Link>
  );
}
