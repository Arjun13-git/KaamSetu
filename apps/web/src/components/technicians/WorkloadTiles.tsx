import { WORKLOAD_STATUSES, type Workload } from "@/lib/technician";
import { statusLabel } from "@/lib/status";
import { StatusDot } from "@/components/ui/Badge";

export function WorkloadTiles({ workload }: { workload: Workload }) {
  return (
    <ul className="grid grid-cols-4 gap-2" aria-label="Workload">
      {WORKLOAD_STATUSES.map((status) => (
        <li key={status} className="rounded-lg bg-sunken/70 px-2 py-2 text-center">
          <p className="text-xl font-semibold tabular-nums">{workload.byStatus[status]}</p>
          <p className="flex items-center justify-center gap-1 text-[11px] leading-tight text-ink-2">
            <StatusDot status={status} className="size-1.5" />
            {statusLabel(status)}
          </p>
        </li>
      ))}
    </ul>
  );
}
