import Link from "next/link";

import { cn } from "@/lib/cn";
import type { Technician } from "@/lib/api/types";

export function TechnicianFilter({ technicians, selected }: { technicians: Technician[]; selected: string | null }) {
  const active = technicians.filter((t) => t.active);
  if (active.length === 0) return null;
  const chip = (href: string, label: string, on: boolean) => (
    <Link
      key={href}
      href={href}
      aria-current={on ? "true" : undefined}
      className={cn(
        "rounded-full border px-3 py-1 text-sm transition-colors",
        on ? "border-brand bg-brand-tint font-medium text-brand-strong" : "border-line bg-surface text-ink-2 hover:bg-sunken",
      )}
    >
      {label}
    </Link>
  );
  return (
    <nav aria-label="Filter by technician" className="flex flex-wrap items-center gap-2">
      {chip("/", "Everyone", !selected)}
      {active.map((t) => chip(`/?tech=${t.technician_id}`, t.name.split(" ")[0], selected === t.technician_id))}
    </nav>
  );
}
