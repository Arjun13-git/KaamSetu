import { ArrowRight, BriefcaseBusiness, FlaskConical, MessageSquareQuote, Sparkles, TextCursorInput } from "lucide-react";

import { UnderstandingCard } from "@/components/intake/UnderstandingCard";
import { AiTag, SeededTag } from "@/components/ui/Ai";
import { Card, SectionLabel } from "@/components/ui/Card";
import type { ParsedExtraction } from "@/lib/extraction";
import type { Provenance } from "@/lib/views";

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
  origin,
}: {
  rawText: string;
  receivedLabel: string;
  understoodAs: string | null;
  extraction: ParsedExtraction | null;
  timeLabel: string | null;
  safety: boolean;
  jobDescription: string;
  origin: Provenance;
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
        {origin.kind === "ai" || origin.kind === "intake" ? (
          <div className="rounded-lg border border-ai-line bg-ai-tint/60 p-3">
            <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-ai-strong uppercase">
              <Sparkles className="size-3.5" aria-hidden />
              AI understood
            </p>
            <p className="text-sm text-ink">{understoodAs ?? "No AI reading was recorded for this request."}</p>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-line-strong bg-surface p-3">
            <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-wider text-ink-2 uppercase">
              {origin.kind === "seeded" ? <FlaskConical className="size-3.5" aria-hidden /> : <TextCursorInput className="size-3.5" aria-hidden />}
              {origin.kind === "seeded" ? "Seeded reading" : "No AI reading"}
            </p>
            <p className="text-sm text-ink">
              {origin.kind === "seeded"
                ? (understoodAs ?? "A hand-written demo reading.")
                : "This job was not read by the AI: the customer's words were used as they are."}
            </p>
            {origin.kind === "seeded" ? <p className="mt-1 text-xs text-ink-3">Hand-written demo data, not model output.</p> : null}
          </div>
        )}
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
          <summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 text-sm font-medium text-ink-2 select-none hover:text-ink">
            {origin.kind === "seeded" ? <SeededTag /> : <AiTag>Everything the AI read</AiTag>}
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
