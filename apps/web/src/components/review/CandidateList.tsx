import Link from "next/link";
import { ChevronRight } from "lucide-react";

import type { CandidateView } from "@/lib/views";

/** Options a person can pick. Nothing here is chosen for them: each is a link that confirms it. */
export function CandidateList({
  items,
  hrefFor,
  verb = "Use",
}: {
  items: Array<CandidateView & { note?: string | null }>;
  hrefFor: (id: string) => string;
  verb?: string;
}) {
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line">
      {items.map((item) => (
        <li key={item.id}>
          <Link href={hrefFor(item.id)} className="flex items-center justify-between gap-3 bg-surface px-3.5 py-3 hover:bg-sunken">
            <span className="min-w-0">
              <span className="block text-sm font-medium">{item.title}</span>
              {item.detail ? <span className="block truncate text-xs text-ink-3">{item.detail}</span> : null}
              {item.reasons.length > 0 ? <span className="mt-0.5 block text-xs text-ink-2">{item.reasons.join(" · ")}</span> : null}
            </span>
            <span className="flex shrink-0 items-center gap-2 text-sm font-medium text-brand-strong">
              {item.score > 0 ? <span className="text-xs font-normal text-ink-3">{Math.round(item.score * 100)}% match</span> : null}
              {verb}
              <ChevronRight className="size-4" aria-hidden />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
