import { Card } from "@/components/ui/Card";
import { Stage, StageLabel } from "./Stage";

const STEPS = [
  { tone: "brand", title: "Customer", text: "Found from the phone number. A name alone is never enough to be sure." },
  { tone: "brand", title: "Appliance", text: "Matched within that customer's own appliances, by type and brand." },
  { tone: "memory", title: "Service memory", text: "What was recorded the last time this appliance was serviced." },
  { tone: "ai", title: "AI understanding", text: "The problem, symptoms and timing, with what is still unknown." },
  { tone: "brand", title: "Job", text: "Created when it is clear, or held for a person when it is not." },
] as const;

/** Before anything is sent: what will happen to the message, so the transformation is expected. */
export function PipelinePreview() {
  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold tracking-tight">From a message to a job</h2>
      <p className="mb-5 max-w-xl text-ink-2">
        Paste what a customer sent. KaamSetu reads it, recognises the customer and their appliance, recalls what was done to that
        appliance before, and turns the message into work.
      </p>
      <ol className="opacity-90">
        {STEPS.map((step, i) => (
          <Stage key={step.title} index={i + 1} tone={step.tone} last={i === STEPS.length - 1}>
            <StageLabel>{step.title}</StageLabel>
            <Card className="border-dashed bg-surface/60 p-3.5 text-sm text-ink-2 shadow-none">{step.text}</Card>
          </Stage>
        ))}
      </ol>
    </div>
  );
}
