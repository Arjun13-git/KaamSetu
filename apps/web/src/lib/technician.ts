// A technician's queue, derived from their jobs. Pure: it sorts and counts what the API returned and
// decides nothing about jobs. "Today" is the business's calendar day, not the server's.

import type { Job, JobStatus } from "./api/types.ts";
import { localDate } from "./format.ts";

export const WORKLOAD_STATUSES = ["ASSIGNED", "SCHEDULED", "ON_THE_WAY", "IN_PROGRESS"] as const satisfies readonly JobStatus[];
export type WorkloadStatus = (typeof WORKLOAD_STATUSES)[number];

export interface Workload {
  open: number;
  today: number;
  byStatus: Record<WorkloadStatus, number>;
}

export interface TechnicianQueue {
  today: Job[];
  later: Job[];
  recentlyCompleted: Job[];
  workload: Workload;
}

const isOpen = (job: Job): boolean => (WORKLOAD_STATUSES as readonly string[]).includes(job.status);
const ACTIVE_RANK: Record<string, number> = { IN_PROGRESS: 0, ON_THE_WAY: 1 };

function startOf(job: Job): number {
  return job.scheduled_slot ? Date.parse(job.scheduled_slot.start) : Number.POSITIVE_INFINITY;
}

/** Work that is happening now, or booked for today, belongs to today. */
function isToday(job: Job, tz: string, now: Date): boolean {
  if (job.status === "IN_PROGRESS" || job.status === "ON_THE_WAY") return true;
  return job.scheduled_slot !== null && localDate(job.scheduled_slot.start, tz) === localDate(now, tz);
}

export function buildQueue(jobs: Job[], tz: string, now: Date, completedLimit = 3): TechnicianQueue {
  const open = jobs.filter(isOpen);
  const today = open
    .filter((job) => isToday(job, tz, now))
    .sort((a, b) => (ACTIVE_RANK[a.status] ?? 2) - (ACTIVE_RANK[b.status] ?? 2) || startOf(a) - startOf(b));
  const todayIds = new Set(today.map((job) => job.job_id));
  const later = open.filter((job) => !todayIds.has(job.job_id)).sort((a, b) => startOf(a) - startOf(b) || Date.parse(a.created_at) - Date.parse(b.created_at));
  const recentlyCompleted = jobs
    .filter((job) => job.status === "COMPLETED" && job.completed_at)
    .sort((a, b) => Date.parse(b.completed_at ?? "") - Date.parse(a.completed_at ?? ""))
    .slice(0, completedLimit);
  return { today, later, recentlyCompleted, workload: workloadOf(jobs, tz, now) };
}

export function workloadOf(jobs: Job[], tz: string, now: Date): Workload {
  const byStatus = Object.fromEntries(WORKLOAD_STATUSES.map((status) => [status, 0])) as Record<WorkloadStatus, number>;
  let openCount = 0;
  let todayCount = 0;
  for (const job of jobs) {
    if (!isOpen(job)) continue;
    openCount += 1;
    byStatus[job.status as WorkloadStatus] += 1;
    if (isToday(job, tz, now)) todayCount += 1;
  }
  return { open: openCount, today: todayCount, byStatus };
}
