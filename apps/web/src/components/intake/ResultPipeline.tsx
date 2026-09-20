import { ChevronDown, Sparkles } from "lucide-react";

import { ServiceMemoryRail } from "@/components/memory/ServiceMemoryRail";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { SafetyBanner } from "@/components/ui/Safety";
import type { IntakeView } from "@/lib/views";
import { JobOutcomeCard } from "./JobOutcomeCard";
import { ResolutionCard } from "./ResolutionCard";
import { Stage, StageLabel } from "./Stage";
import { UnderstandingCard } from "./UnderstandingCard";

/**
 * "What KaamSetu did", in the order it happened: who, which appliance, what was done to it before,
 * what the message means, and what work resulted. The API answers in one response; the stagger is
 * only the order in which that answer is shown.
 */
export function ResultPipeline({ view }: { view: IntakeView }) {
  const critical = view.safety || view.job?.urgency === "safety_critical";
  return (
    <div className="space-y-5">
      <Card className="reveal overflow-hidden" style={{ "--i": 0 } as React.CSSProperties}>
        <div className="border-b border-line bg-sunken/60 px-4 py-3">
          <p className="mb-1 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
            Customer wrote{view.phone ? ` · ${view.phone}` : ""}
          </p>
          <p className="text-[15px] text-ink">“{view.rawText}”</p>
        </div>
        <div className="flex items-start gap-3 bg-ai-tint/60 px-4 py-3">
          <Sparkles className="mt-0.5 size-4 shrink-0 text-ai" aria-hidden />
          <div className="min-w-0">
            <p className="text-[11px] font-semibold tracking-wider text-ai-strong uppercase">Understood as</p>
            <p className="font-medium text-ink">
              {view.understoodAs ?? "The message could not be turned into a structured request."}
            </p>
          </div>
        </div>
      </Card>

      {critical ? <SafetyBanner announce /> : null}

      <ol>
        <Stage index={1} tone="brand">
          <StageLabel>Customer</StageLabel>
          <ResolutionCard view={view.customer} />
        </Stage>

        <Stage index={2} tone="brand">
          <StageLabel>Appliance</StageLabel>
          <ResolutionCard view={view.asset} />
        </Stage>

        <Stage index={3} tone="memory">
          <StageLabel>Previous service</StageLabel>
          {view.memory ? (
            <ServiceMemoryRail
              memory={view.memory}
              current={{ label: "This request", text: view.rawText }}
              recalledLabel="Recalled for this request"
            />
          ) : (
            <Card className="border-dashed p-4 text-sm text-ink-2">
              Service memory appears once the appliance is identified. It is always the recorded history of that one appliance.
            </Card>
          )}
        </Stage>

        <Stage index={4} tone="ai">
          <StageLabel right={<Badge tone="ai">Proposal to verify</Badge>}>AI understanding</StageLabel>
          {view.understanding ? (
            <UnderstandingCard
              extraction={view.understanding.extraction}
              timeLabel={view.understanding.timeLabel}
              safety={view.safety}
            />
          ) : (
            <Card className="border-dashed p-4 text-sm text-ink-2">No AI reading is recorded for this request.</Card>
          )}
        </Stage>

        <Stage index={5} tone={critical ? "safety" : "brand"} last>
          <StageLabel>Job</StageLabel>
          <JobOutcomeCard view={view} />
        </Stage>
      </ol>
      <p className="flex items-center justify-center gap-1 text-xs text-ink-3">
        <ChevronDown className="size-3.5" aria-hidden />
        {view.job ? "Saved as a service request. The job now moves through the board." : "Saved as a service request, waiting for a person to review it."}
      </p>
    </div>
  );
}
