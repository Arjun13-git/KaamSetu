// The job board's view model. Pure: it takes what the API returned (jobs, and lookups for the names
// the API leaves as ids) and returns columns of display-ready cards. It decides nothing about jobs.

import type { Asset, Customer, Job, JobStatus, ServiceRequest, Technician } from "./api/types.ts";
import { parseExtraction } from "./extraction.ts";
import { applianceLabel, formatSlot, initials, relativeTime } from "./format.ts";
import { BOARD_STATUSES } from "./status.ts";

export interface BoardCard {
  id: string;
  href: string;
  description: string;
  status: JobStatus;
  urgency: Job["urgency"];
  customerName: string;
  appliance: string | null;
  technician: { name: string; initials: string } | null;
  slot: { label: string; kind: "scheduled" | "preferred" } | null;
  ageLabel: string;
  /** Completed jobs recorded for the same appliance: the count behind the Service Memory badge. */
  pastServices: number;
}

export interface ReviewRow {
  id: string;
  text: string;
  reason: string;
  ageLabel: string;
  /** The reading is a hand-written demo fixture, not something a model produced. */
  seeded: boolean;
}

export interface BoardView {
  columns: Array<{ status: JobStatus; cards: BoardCard[] }>;
  finished: { completed: BoardCard[]; cancelled: BoardCard[] };
  attention: { safety: BoardCard[]; review: ReviewRow[] };
  openCount: number;
}

export interface BoardLookups {
  customers: Map<string, Customer>;
  assets: Map<string, Asset>;
  technicians: Map<string, Technician>;
}

const URGENCY_RANK: Record<Job["urgency"], number> = { safety_critical: 0, high: 1, normal: 2, low: 3 };

function toCard(job: Job, lookups: BoardLookups, pastServices: number, tz: string, now: Date): BoardCard {
  const asset = lookups.assets.get(job.asset_id);
  const technician = job.technician_id ? lookups.technicians.get(job.technician_id) : undefined;
  const scheduled = formatSlot(job.scheduled_slot, tz, now);
  const preferred = formatSlot(job.preferred_slot, tz, now);
  return {
    id: job.job_id,
    href: `/jobs/${job.job_id}`,
    description: job.description,
    status: job.status,
    urgency: job.urgency,
    customerName: lookups.customers.get(job.customer_id)?.name ?? "Unknown customer",
    appliance: asset ? applianceLabel(asset) : null,
    technician: job.technician_id
      ? { name: technician?.name ?? "Technician", initials: initials(technician?.name ?? "T") }
      : null,
    slot: scheduled
      ? { label: scheduled, kind: "scheduled" }
      : preferred
        ? { label: preferred, kind: "preferred" }
        : null,
    ageLabel: relativeTime(job.created_at, now),
    pastServices,
  };
}

/** Safety-critical first, then oldest first: the order a dispatcher works a queue. */
function queueOrder(a: Job, b: Job): number {
  return URGENCY_RANK[a.urgency] - URGENCY_RANK[b.urgency] || Date.parse(a.created_at) - Date.parse(b.created_at);
}

export function reviewReason(request: ServiceRequest): string {
  const { customer_resolution: c, asset_resolution: a } = request;
  if (request.status === "EXTRACTION_FAILED") return "The AI could not read this";
  if (c.state === "new") return "New customer";
  if (c.state === "ambiguous") return "Which customer?";
  if (c.state === "unresolved") return "Customer not identified";
  if (a.state === "ambiguous") return "Which appliance?";
  if (a.state === "new") return "New appliance";
  return "Needs a decision";
}

export function buildBoard(
  jobs: Job[],
  requestsToReview: ServiceRequest[],
  lookups: BoardLookups,
  options: { technicianId?: string | null; tz: string; now: Date },
): BoardView {
  const { tz, now } = options;
  const completedByAsset = new Map<string, number>();
  for (const job of jobs) {
    if (job.status === "COMPLETED") completedByAsset.set(job.asset_id, (completedByAsset.get(job.asset_id) ?? 0) + 1);
  }
  const card = (job: Job) => toCard(job, lookups, completedByAsset.get(job.asset_id) ?? 0, tz, now);
  const scoped = options.technicianId ? jobs.filter((j) => j.technician_id === options.technicianId) : jobs;

  const columns = BOARD_STATUSES.map((status) => ({
    status,
    cards: scoped
      .filter((j) => j.status === status)
      .sort(queueOrder)
      .map(card),
  }));
  const byRecent = (a: Job, b: Job) => Date.parse(b.updated_at) - Date.parse(a.updated_at);
  const open = jobs.filter((j) => j.status !== "COMPLETED" && j.status !== "CANCELLED");

  return {
    columns,
    finished: {
      completed: scoped.filter((j) => j.status === "COMPLETED").sort(byRecent).map(card),
      cancelled: scoped.filter((j) => j.status === "CANCELLED").sort(byRecent).map(card),
    },
    attention: {
      safety: open.filter((j) => j.urgency === "safety_critical").sort(queueOrder).map(card),
      review: requestsToReview
        .filter((r) => r.status === "NEEDS_REVIEW" || r.status === "EXTRACTION_FAILED")
        .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
        .map((r) => ({
          id: r.service_request_id,
          text: r.raw_text,
          reason: reviewReason(r),
          ageLabel: relativeTime(r.created_at, now),
          seeded: parseExtraction(r.extraction)?.isFixture === true,
        })),
    },
    openCount: open.length,
  };
}
