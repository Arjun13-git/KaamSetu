import { CircleAlert, Info } from "lucide-react";

import { AiTag, ConfidenceMeter, ProvenanceChip, UnknownValue } from "@/components/ui/Ai";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { assetTypeLabel, sentenceCase } from "@/lib/format";
import { missingLabel, type ParsedExtraction } from "@/lib/extraction";

function Row({ label, source, children }: { label: string; source?: ParsedExtraction["data"]["sources"][string]; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-xs text-ink-3">
        {label}
        {source ? <ProvenanceChip source={source} /> : null}
      </dt>
      <dd className="mt-0.5 text-sm text-ink">{children}</dd>
    </div>
  );
}

/**
 * What the model read out of the customer's words. Everything here is a proposal for a person to
 * check: values the customer never gave stay unknown, and each field says where it came from.
 */
export function UnderstandingCard({
  extraction,
  timeLabel,
  safety,
}: {
  extraction: ParsedExtraction;
  timeLabel: string | null;
  safety: boolean;
}) {
  const { data } = extraction;
  const sources = data.sources;
  const typeKnown = data.asset.type !== "unknown";
  const urgencyLabel = safety
    ? "Safety-critical (raised by KaamSetu's safety check)"
    : data.problem.urgency
      ? sentenceCase(data.problem.urgency)
      : null;

  return (
    <Card className="border-ai-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <AiTag />
        {extraction.isFixture ? <Badge>Seeded example</Badge> : null}
      </div>

      <dl className="mt-4 grid gap-x-6 gap-y-3.5 sm:grid-cols-2">
        <Row label="Appliance" source={sources["asset.type"]}>
          {typeKnown ? assetTypeLabel(data.asset.type).replace(/^./, (c) => c.toUpperCase()) : <UnknownValue />}
        </Row>
        <Row label="Brand" source={sources["asset.brand"]}>
          {data.asset.brand ?? <UnknownValue />}
        </Row>
        <Row label="Model" source={sources["asset.model"]}>
          {data.asset.model ?? <UnknownValue />}
        </Row>
        <Row label="Type of work" source={sources["service_type"]}>
          {data.serviceType !== "unknown" ? sentenceCase(data.serviceType) : <UnknownValue />}
        </Row>
        <div className="sm:col-span-2">
          <Row label="Problem, as reported" source={sources["problem.description"]}>
            {data.problem.description ?? <UnknownValue />}
          </Row>
        </div>
        <div className="sm:col-span-2">
          <Row label="Symptoms" source={sources["problem.symptoms"]}>
            {data.problem.symptoms.length > 0 ? (
              <span className="flex flex-wrap gap-1.5">
                {data.problem.symptoms.map((symptom) => (
                  <Badge key={symptom} tone="ai">
                    {symptom}
                  </Badge>
                ))}
              </span>
            ) : (
              <UnknownValue />
            )}
          </Row>
        </div>
        <Row label="Urgency" source={sources["problem.urgency"]}>
          {urgencyLabel ?? <UnknownValue />}
        </Row>
        <Row label="Preferred time" source={sources["time_preference"]}>
          {timeLabel ?? <UnknownValue />}
        </Row>
      </dl>

      <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-line pt-4 sm:grid-cols-4">
        <ConfidenceMeter label="Overall" value={data.confidence.overall} />
        <ConfidenceMeter label="Appliance" value={data.confidence.asset} />
        <ConfidenceMeter label="Problem" value={data.confidence.problem} />
        <ConfidenceMeter label="Schedule" value={data.confidence.schedule} />
      </div>

      {data.missingInformation.length > 0 ? (
        <div className="mt-4 border-t border-line pt-4">
          <p className="mb-1.5 text-xs font-medium text-ink-3">Still unknown</p>
          <ul className="flex flex-wrap gap-1.5">
            {data.missingInformation.map((key) => (
              <li key={key} className="rounded-full border border-dashed border-line-strong px-2 py-0.5 text-xs text-ink-2">
                {missingLabel(key)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {extraction.warnings.length > 0 ? (
        <ul className="mt-4 space-y-1 border-t border-line pt-4">
          {extraction.warnings.map((warning) => (
            <li key={warning} className="flex items-start gap-2 text-sm text-ink-2">
              <CircleAlert className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
              <span>KaamSetu adjusted this: {warning}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <details className="group mt-4 border-t border-line pt-3 text-xs text-ink-3">
        <summary className="flex min-h-10 cursor-pointer list-none items-center gap-1.5 select-none hover:text-ink-2">
          <Info className="size-3.5" aria-hidden />
          How this was produced
        </summary>
        <p className="mt-2 font-mono leading-5">
          {extraction.isFixture ? "hand-written demo fixture" : `model ${extraction.modelId}`} · prompt {extraction.promptVersion}
          {extraction.imageSupplied ? " · photo shown to the model" : ""}
        </p>
        <p className="mt-1">
          The model proposes; KaamSetu validates it, decides who and what it refers to, and writes the record.
        </p>
      </details>
    </Card>
  );
}
