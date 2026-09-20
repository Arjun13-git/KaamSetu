"use client";

import { CalendarClock, CircleCheckBig, LoaderCircle, Play, Route, UserPlus, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { assignJobAction, completeJobAction, scheduleJobAction, transitionJobAction, type ActionResult } from "@/app/jobs/[id]/actions";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { friendlyMessage, type ApiFailure } from "@/lib/api/errors";
import { cn } from "@/lib/cn";
import type { JobAction } from "@/lib/status";

export interface TechnicianOption {
  id: string;
  name: string;
  skills: string[];
  active: boolean;
}

type DialogKind = "assign" | "schedule" | "complete" | "cancel" | null;

const ICONS = { assign: UserPlus, schedule: CalendarClock, complete: CircleCheckBig, cancel: XCircle } as const;

function Problem({ failure }: { failure: ApiFailure | null }) {
  if (!failure) return null;
  return (
    <p role="alert" className="mt-3 rounded-lg border border-safety-line bg-safety-tint px-3 py-2 text-sm text-safety-strong">
      {friendlyMessage(failure)}
    </p>
  );
}

const inputClass =
  "w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm placeholder:text-ink-3 focus:border-brand";

/**
 * Lifecycle buttons for one job. Which buttons appear is a hint from the job's status; the API is the
 * authority and anything it refuses is shown here in its own words.
 */
export function JobActions({
  jobId,
  actions,
  technicians,
  currentTechnicianId,
  defaultSlot,
  customerName,
  large,
}: {
  jobId: string;
  actions: JobAction[];
  technicians: TechnicianOption[];
  currentTechnicianId: string | null;
  defaultSlot: string;
  customerName: string;
  /** Bigger tap targets, for a technician on a phone. */
  large?: boolean;
}) {
  const router = useRouter();
  const [dialog, setDialog] = useState<DialogKind>(null);
  const [failure, setFailure] = useState<ApiFailure | null>(null);
  const [pending, startTransition] = useTransition();
  const [busyLabel, setBusyLabel] = useState<string | null>(null);

  const [technicianId, setTechnicianId] = useState("");
  const [slot, setSlot] = useState(defaultSlot);
  const [work, setWork] = useState("");
  const [notes, setNotes] = useState("");
  const [parts, setParts] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [followUp, setFollowUp] = useState(false);

  function close() {
    setDialog(null);
    setFailure(null);
  }

  function perform(label: string, work: () => Promise<ActionResult>) {
    setFailure(null);
    setBusyLabel(label);
    startTransition(async () => {
      const result = await work();
      if (result.ok) {
        setDialog(null);
        router.refresh();
      } else {
        setFailure(result.failure);
        // A conflict means the job changed under us: show the truth again.
        if (result.failure.status === 409) router.refresh();
      }
      setBusyLabel(null);
    });
  }

  if (actions.length === 0) return null;
  const [primary, ...rest] = actions;

  function press(action: JobAction) {
    setFailure(null);
    if (action.kind === "transition") perform(action.label, () => transitionJobAction(jobId, action.to));
    else setDialog(action.kind);
  }

  const renderButton = (action: JobAction, isPrimary: boolean) => {
    const Icon = action.kind === "transition" ? (action.to === "ON_THE_WAY" ? Route : Play) : ICONS[action.kind];
    const busy = pending && busyLabel === action.label;
    return (
      <Button
        key={action.label}
        variant={isPrimary ? "primary" : action.kind === "cancel" ? "danger" : "secondary"}
        size={large ? "lg" : undefined}
        className={large ? "min-w-40 flex-1" : undefined}
        onClick={() => press(action)}
        disabled={pending}
      >
        {busy ? <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden /> : <Icon className="size-4" aria-hidden />}
        {action.label}
      </Button>
    );
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        {renderButton(primary, true)}
        {rest.map((action) => renderButton(action, false))}
      </div>
      {dialog === null ? <Problem failure={failure} /> : null}

      <Dialog open={dialog === "assign"} onClose={close} title="Assign a technician" description={`Who should visit ${customerName}?`}>
        <fieldset className="space-y-2">
          <legend className="sr-only">Technician</legend>
          {technicians.map((tech) => (
            <label
              key={tech.id}
              className={cn(
                "flex items-center gap-3 rounded-lg border px-3 py-2.5",
                !tech.active
                  ? "cursor-not-allowed border-line bg-sunken/60 text-ink-3"
                  : technicianId === tech.id
                    ? "cursor-pointer border-brand bg-brand-tint"
                    : "cursor-pointer border-line hover:bg-sunken",
              )}
            >
              <input
                type="radio"
                name="technician"
                value={tech.id}
                checked={technicianId === tech.id}
                disabled={!tech.active}
                onChange={() => setTechnicianId(tech.id)}
                className="accent-(--color-brand)"
              />
              <span className="min-w-0 flex-1">
                <span className={cn("block text-sm font-medium", !tech.active && "text-ink-3")}>
                  {tech.name}
                  {tech.id === currentTechnicianId ? <span className="ml-2 text-xs font-normal text-ink-3">current</span> : null}
                </span>
                <span className="block truncate text-xs text-ink-3">{tech.skills.map((s) => s.replace(/_/g, " ")).join(" · ") || "No skills listed"}</span>
              </span>
              {tech.active ? null : <Badge>Inactive</Badge>}
            </label>
          ))}
        </fieldset>
        <Problem failure={failure} />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!technicianId || pending} onClick={() => perform("assign", () => assignJobAction(jobId, technicianId))}>
            {pending ? <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden /> : null}
            Assign
          </Button>
        </div>
      </Dialog>

      <Dialog open={dialog === "schedule"} onClose={close} title="Schedule the visit" description="Times are in the business's timezone.">
        <label htmlFor="slot" className="mb-1.5 block text-sm font-medium">
          Visit starts
        </label>
        <input id="slot" type="datetime-local" value={slot} onChange={(e) => setSlot(e.target.value)} className={inputClass} />
        <Problem failure={failure} />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!slot || pending} onClick={() => perform("schedule", () => scheduleJobAction(jobId, slot))}>
            {pending ? <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden /> : null}
            Schedule
          </Button>
        </div>
      </Dialog>

      <Dialog
        open={dialog === "complete"}
        onClose={close}
        title="Complete the job"
        description="This records a service event. It becomes part of this appliance's Service Memory."
      >
        <div className="space-y-3">
          <div>
            <label htmlFor="work" className="mb-1.5 block text-sm font-medium">
              Work performed <span className="text-safety">*</span>
            </label>
            <textarea id="work" rows={3} value={work} onChange={(e) => setWork(e.target.value)} placeholder="What was actually done" className={inputClass} />
          </div>
          <div>
            <label htmlFor="notes" className="mb-1.5 block text-sm font-medium">
              Technician notes
            </label>
            <textarea id="notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Anything the next visit should know" className={inputClass} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="parts" className="mb-1.5 block text-sm font-medium">
                Parts used
              </label>
              <input id="parts" value={parts} onChange={(e) => setParts(e.target.value)} placeholder="Comma separated" className={inputClass} />
            </div>
            <div>
              <label htmlFor="symptoms" className="mb-1.5 block text-sm font-medium">
                Symptoms observed
              </label>
              <input id="symptoms" value={symptoms} onChange={(e) => setSymptoms(e.target.value)} placeholder="Comma separated" className={inputClass} />
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={followUp} onChange={(e) => setFollowUp(e.target.checked)} className="size-4 accent-(--color-brand)" />
            A follow-up visit is needed
          </label>
        </div>
        <Problem failure={failure} />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={!work.trim() || pending}
            onClick={() => perform("complete", () => completeJobAction(jobId, { workPerformed: work, notes, parts, symptoms, followUp }))}
          >
            {pending ? <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden /> : <CircleCheckBig className="size-4" aria-hidden />}
            Complete job
          </Button>
        </div>
      </Dialog>

      <Dialog open={dialog === "cancel"} onClose={close} title="Cancel this job?" description="A cancelled job cannot be reopened. The request and its history are kept.">
        <Problem failure={failure} />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={close}>
            Keep job
          </Button>
          <Button variant="danger" disabled={pending} onClick={() => perform("cancel", () => transitionJobAction(jobId, "CANCELLED"))}>
            {pending ? <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden /> : <XCircle className="size-4" aria-hidden />}
            Cancel job
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
