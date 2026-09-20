import Link from "next/link";
import { CircleCheck, CircleHelp, CirclePlus, ArrowUpRight } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { cn } from "@/lib/cn";
import type { ResolutionView } from "@/lib/views";

const STATE = {
  existing: { label: "Existing", tone: "ok" as const, Icon: CircleCheck, iconClass: "text-ok" },
  new: { label: "New", tone: "brand" as const, Icon: CirclePlus, iconClass: "text-brand" },
  ambiguous: { label: "Needs confirmation", tone: "neutral" as const, Icon: CircleHelp, iconClass: "text-ink" },
  unresolved: { label: "Not identified", tone: "neutral" as const, Icon: CircleHelp, iconClass: "text-ink-3" },
};

function score(value: number): string {
  return `${Math.round(value * 100)}% match`;
}

/**
 * Customer and appliance resolution. This is the application's decision from recorded evidence
 * (a phone number, a brand), not the model's, so it is green/teal rather than AI blue. Anything
 * short of certain is shown as needing a person, never silently attached.
 */
export function ResolutionCard({ view }: { view: ResolutionView }) {
  const state = STATE[view.state];
  const Icon = state.Icon;
  const title = (
    <span className="font-semibold text-ink">{view.title}</span>
  );
  return (
    <Card className={cn("p-4", view.state === "ambiguous" && "border-ink-3")}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Icon className={cn("mt-0.5 size-5 shrink-0", state.iconClass)} aria-hidden />
          <div className="min-w-0">
            {view.href ? (
              <Link href={view.href} className="group inline-flex items-center gap-1 hover:underline">
                {title}
                <ArrowUpRight className="size-3.5 text-ink-3 group-hover:text-ink" aria-hidden />
              </Link>
            ) : (
              title
            )}
            {view.detail ? <p className="mt-0.5 text-sm text-ink-2">{view.detail}</p> : null}
          </div>
        </div>
        <Badge tone={state.tone}>{state.label}</Badge>
      </div>

      {view.state === "existing" && (view.reasons.length > 0 || view.score !== null) ? (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 pl-8">
          {view.reasons.map((reason) => (
            <Badge key={reason}>{reason}</Badge>
          ))}
          {view.score !== null ? <span className="text-xs text-ink-3">{score(view.score)}</span> : null}
        </div>
      ) : null}

      {view.candidates.length > 0 ? (
        <ul className="mt-3 divide-y divide-line rounded-lg border border-line">
          {view.candidates.map((candidate) => (
            <li key={candidate.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5">
              <div className="min-w-0">
                <p className="text-sm font-medium">{candidate.title}</p>
                {candidate.detail ? <p className="text-xs text-ink-3">{candidate.detail}</p> : null}
                {candidate.reasons.length > 0 ? (
                  <p className="mt-0.5 text-xs text-ink-2">{candidate.reasons.join(" · ")}</p>
                ) : null}
              </div>
              <span className="text-xs font-medium text-ink-2">{score(candidate.score)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
