import { cn } from "@/lib/cn";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-(--radius-card) border border-line bg-surface shadow-card", className)} {...props} />;
}

export function SectionLabel({ className, children }: { className?: string; children: React.ReactNode }) {
  return <h2 className={cn("text-xs font-semibold tracking-wide text-ink-3 uppercase", className)}>{children}</h2>;
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{title}</h1>
        {subtitle ? <p className="mt-1 text-ink-2">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
