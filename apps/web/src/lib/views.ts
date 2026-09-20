// View models: what the screens render, already formatted. They are built on the server (times are
// read in the business timezone there), so client components receive plain strings and never need
// the timezone, the clock, or any configuration. Everything here is pure and unit-tested.

import type { IntakeOutcome, JobStatus, ResolutionState, ServiceEvent, Urgency } from "./api/types.ts";
import { describeTimePreference, formatDate, relativeTime, assetTypeLabel } from "./format.ts";
import type { ParsedExtraction } from "./extraction.ts";

export interface MemoryEventView {
  id: string;
  jobId: string;
  dateLabel: string;
  agoLabel: string;
  work: string;
  notes: string | null;
  reported: string[];
  parts: string[];
  followUp: boolean;
  technician: string | null;
}

export interface MemoryView {
  assetId: string;
  assetLabel: string;
  events: MemoryEventView[];
  lastServiceAgo: string | null;
}

export function toMemoryEvent(
  event: ServiceEvent,
  technicianName: string | null,
  tz: string,
  now: Date,
): MemoryEventView {
  return {
    id: event.event_id,
    jobId: event.job_id,
    dateLabel: formatDate(event.timestamp, tz),
    agoLabel: relativeTime(event.timestamp, now),
    work: event.work_performed,
    notes: event.technician_notes,
    reported: event.observed_symptoms,
    parts: event.parts_used,
    followUp: event.follow_up_required,
    technician: technicianName,
  };
}

/** Newest first, as the API returns them. `lastServiceAgo` comes from the newest event only. */
export function toMemory(
  assetId: string,
  assetLabel: string,
  events: ServiceEvent[],
  technicianNames: Map<string, string>,
  tz: string,
  now: Date,
): MemoryView {
  const ordered = [...events].sort((a, b) => Date.parse(b.timestamp) - Date.parse(a.timestamp));
  return {
    assetId,
    assetLabel,
    events: ordered.map((e) => toMemoryEvent(e, technicianNames.get(e.technician_id) ?? null, tz, now)),
    lastServiceAgo: ordered[0] ? relativeTime(ordered[0].timestamp, now) : null,
  };
}

export interface CandidateView {
  id: string;
  title: string;
  detail: string | null;
  score: number;
  reasons: string[];
  href: string | null;
}

export interface ResolutionView {
  kind: "customer" | "asset";
  state: ResolutionState;
  title: string;
  detail: string | null;
  reasons: string[];
  score: number | null;
  href: string | null;
  candidates: CandidateView[];
}

export interface JobSummaryView {
  id: string;
  description: string;
  status: JobStatus;
  urgency: Urgency;
  slotLabel: string | null;
  href: string;
}

export interface IntakeView {
  outcome: IntakeOutcome;
  serviceRequestId: string;
  safety: boolean;
  rawText: string;
  phone: string | null;
  understoodAs: string | null;
  customer: ResolutionView;
  asset: ResolutionView;
  memory: MemoryView | null;
  understanding: { extraction: ParsedExtraction; timeLabel: string | null } | null;
  job: JobSummaryView | null;
  reviewReasons: string[];
  failureReason: string | null;
}

/** "LG air conditioner · AC is not cooling again · Tomorrow, from 5:00 pm", from what was extracted. */
export function understoodAs(extraction: ParsedExtraction | null, tz: string, now: Date): string | null {
  if (!extraction) return null;
  const { asset, problem, timePreference } = extraction.data;
  const parts: string[] = [];
  if (asset.type !== "unknown") {
    const type = assetTypeLabel(asset.type);
    parts.push(asset.brand ? `${asset.brand} ${type}` : type);
  }
  if (problem.description) parts.push(problem.description);
  const when = describeTimePreference(timePreference, tz, now);
  if (when) parts.push(when);
  return parts.length > 0 ? parts.join(" · ") : null;
}

/**
 * Why a request has no job yet, in words a person can act on. This explains what the API already
 * decided from the recorded resolution states; it does not re-decide anything.
 */
export function reviewReasons(
  outcome: IntakeOutcome,
  customer: ResolutionState,
  asset: ResolutionState,
): string[] {
  if (outcome === "job_created") return [];
  const reasons: string[] = [];
  if (customer === "ambiguous") reasons.push("Choose which customer this is");
  else if (customer === "new") reasons.push("This looks like a new customer: add them before a job is created");
  else if (customer === "unresolved") reasons.push("The customer could not be identified");
  if (asset === "ambiguous") reasons.push("Choose which appliance this is about");
  else if (asset === "new" && customer === "existing") reasons.push("This appliance is not on file for this customer yet");
  else if (asset === "unresolved" && customer === "existing") reasons.push("The appliance could not be identified");
  if (reasons.length === 0 && outcome === "needs_review") {
    reasons.push("The AI was not confident enough to create the job unattended");
  }
  return reasons;
}
