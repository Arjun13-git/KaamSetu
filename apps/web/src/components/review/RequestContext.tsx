import { CircleAlert } from "lucide-react";

import { UnderstandingCard } from "@/components/intake/UnderstandingCard";
import { AiTag } from "@/components/ui/Ai";
import { Badge } from "@/components/ui/Badge";
import { Card, SectionLabel } from "@/components/ui/Card";
import { SafetyBanner } from "@/components/ui/Safety";
import type { ParsedExtraction } from "@/lib/extraction";
import type { Provenance } from "@/lib/views";

/** What the review is about, kept in view while a person decides: the words, the phone, the reading. */
export function RequestContext({
  rawText,
  phone,
  receivedLabel,
  understood,
  extraction,
  timeLabel,
  origin,
  safety,
  failureReason,
}: {
  rawText: string;
  phone: string;
  receivedLabel: string;
  understood: string | null;
  extraction: ParsedExtraction | null;
  timeLabel: string | null;
  origin: Provenance;
  safety: boolean;
  failureReason: string | null;
}) {
  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        <div className="border-b border-line bg-sunken/60 px-4 py-3">
          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
            <SectionLabel>Customer wrote</SectionLabel>
            <Badge tone={origin.kind === "ai" ? "ai" : "neutral"}>{origin.label}</Badge>
          </div>
          <p className="text-[15px] text-ink">“{rawText}”</p>
          <p className="mt-2 text-xs text-ink-3">
            {receivedLabel} · {phone ? `Phone ${phone}` : "No phone number was kept with this request"}
          </p>
        </div>
        {understood ? (
          <div className="bg-ai-tint/60 px-4 py-3">
            <AiTag>Understood as</AiTag>
            <p className="mt-1.5 font-medium text-ink">{understood}</p>
          </div>
        ) : (
          <div className="flex items-start gap-2 px-4 py-3 text-sm text-ink-2">
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
            <span>
              {failureReason ? "The AI could not read this message. It is saved exactly as written." : "No AI reading is recorded for this request."}
            </span>
          </div>
        )}
      </Card>
      {safety ? <SafetyBanner /> : null}
      {extraction ? (
        <details className="group rounded-(--radius-card) border border-line bg-surface shadow-card">
          <summary className="flex min-h-11 cursor-pointer list-none items-center px-4 py-3 text-sm font-medium text-ink-2 select-none hover:text-ink">
            Everything the AI read <span className="font-normal text-ink-3">· fields, confidence, what is unknown</span>
          </summary>
          <div className="border-t border-line p-3">
            <UnderstandingCard extraction={extraction} timeLabel={timeLabel} safety={safety} />
          </div>
        </details>
      ) : null}
    </div>
  );
}
