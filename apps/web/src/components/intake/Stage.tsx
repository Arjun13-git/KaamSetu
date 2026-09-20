import { cn } from "@/lib/cn";

const NODE = {
  neutral: "border-line-strong bg-surface text-ink-2",
  brand: "border-brand bg-brand text-white",
  ai: "border-ai bg-ai text-white",
  memory: "border-memory bg-memory text-white",
  safety: "border-safety bg-safety text-white",
} as const;

export type StageTone = keyof typeof NODE;

/** One numbered step of the result, on a vertical line so the order the work happened is visible. */
export function Stage({
  index,
  tone = "neutral",
  last,
  children,
}: {
  index: number;
  tone?: StageTone;
  last?: boolean;
  children: React.ReactNode;
}) {
  return (
    <li className="reveal grid grid-cols-[2rem_minmax(0,1fr)] gap-3" style={{ "--i": index } as React.CSSProperties}>
      <div className="relative flex flex-col items-center">
        <span className={cn("z-10 grid size-8 shrink-0 place-items-center rounded-full border-2 text-sm font-semibold", NODE[tone])}>
          {index}
        </span>
        {last ? null : <span aria-hidden className="mt-1 w-0.5 flex-1 rounded bg-line-strong" />}
      </div>
      <div className={cn("min-w-0", last ? "" : "pb-5")}>{children}</div>
    </li>
  );
}

export function StageLabel({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <div className="mb-2 flex min-h-8 items-center justify-between gap-2">
      <h3 className="text-xs font-semibold tracking-wider text-ink-3 uppercase">{children}</h3>
      {right}
    </div>
  );
}
