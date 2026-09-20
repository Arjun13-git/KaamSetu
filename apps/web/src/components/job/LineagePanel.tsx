import { ArrowRight, BriefcaseBusiness, MessageSquareQuote, Sparkles } from "lucide-react";

import { UnderstandingCard } from "@/components/intake/UnderstandingCard";
import { AiTag } from "@/components/ui/Ai";
import { Card, SectionLabel } from "@/components/ui/Card";
import type { ParsedExtraction } from "@/lib/extraction";

/**
 * How this job came to be: the customer's own words, what the AI read from them, and the job that
 * resulted. It keeps the original message one glance away from the work order.
 */
export function LineagePanel({
  rawText,
  receivedLabel,
  understoodAs,
  extraction,
  timeLabel,
  safety,
  jobDescription,
}: {
  rawText: string;
  receivedLabel: string;
  understoodAs: string | null;
  extraction: ParsedExtraction | null;
  timeLabel: string | null;
  safety: boolean;
  jobDescription: string;
}) {
  return (
    <Card className="p-4">
      <SectionLabel className="mb-3">From the customer&rsquo;s words to this job</SectionLabel>
      <div className="grid items-stretch gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr]">
        <div className="rounded-lg bg-sunken/70 p-3">
          <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
            <MessageSquareQuote className="size-3.5" aria-hidden />
            Customer wrote · {receivedLabel}
          </p>
          <p className="text-sm text-ink">“{rawText}”</p>
        </div>
        <ArrowRight className="hidden size-4 self-center text-ink-3 lg:block" aria-hidden />
        <div className="rounded-lg border border-ai-line bg-ai-tint/60 p-3">
          <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-ai-strong uppercase">
            <Sparkles className="size-3.5" aria-hidden />
            AI understood
          </p>
          <p className="text-sm text-ink">{understoodAs ?? "No AI reading was recorded for this request."}</p>
        </div>
        <ArrowRight className="hidden size-4 self-center text-ink-3 lg:block" aria-hidden />
        <div className="rounded-lg border border-brand/40 bg-brand-tint/50 p-3">
          <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-brand-strong uppercase">
            <BriefcaseBusiness className="size-3.5" aria-hidden />
            Job
          </p>
          <p className="text-sm font-medium text-ink">{jobDescription}</p>
        </div>
      </div>
      {extraction ? (
        <details className="mt-3 border-t border-line pt-3">
          <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-ink-2 select-none hover:text-ink">
            <AiTag>Everything the AI read</AiTag>
            <span className="text-xs font-normal text-ink-3">Fields, confidence and what is still unknown</span>
          </summary>
          <div className="mt-3">
            <UnderstandingCard extraction={extraction} timeLabel={timeLabel} safety={safety} />
          </div>
        </details>
      ) : null}
    </Card>
  );
}
