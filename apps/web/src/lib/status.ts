// Job status presentation and the *hints* about what a person can do next. The API stays the
// authority: its state machine (services/api/app/domain/job_state_machine.py) decides every
// transition, and anything it refuses is shown to the person as the API's own message.

import type { JobStatus } from "./api/types.ts";

export const BOARD_STATUSES: JobStatus[] = ["NEW", "ASSIGNED", "SCHEDULED", "ON_THE_WAY", "IN_PROGRESS"];
export const PROGRESS_STEPS: JobStatus[] = ["NEW", "ASSIGNED", "SCHEDULED", "ON_THE_WAY", "IN_PROGRESS", "COMPLETED"];

const LABELS: Record<JobStatus, string> = {
  NEW: "New",
  ASSIGNED: "Assigned",
  SCHEDULED: "Scheduled",
  ON_THE_WAY: "On the way",
  IN_PROGRESS: "In progress",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export function statusLabel(status: JobStatus): string {
  return LABELS[status];
}

export function isTerminal(status: JobStatus): boolean {
  return status === "COMPLETED" || status === "CANCELLED";
}

export type JobAction =
  | { kind: "assign"; label: string }
  | { kind: "schedule"; label: string }
  | { kind: "transition"; to: "ON_THE_WAY" | "IN_PROGRESS"; label: string }
  | { kind: "complete"; label: string }
  | { kind: "cancel"; label: string };

/** The next steps a person would reasonably take from each status. */
export function nextActions(status: JobStatus, hasTechnician: boolean): JobAction[] {
  switch (status) {
    case "NEW":
      return [
        { kind: "assign", label: "Assign technician" },
        { kind: "cancel", label: "Cancel job" },
      ];
    case "ASSIGNED":
      return [
        { kind: "schedule", label: "Schedule visit" },
        { kind: "transition", to: "ON_THE_WAY", label: "Mark on the way" },
        { kind: "assign", label: hasTechnician ? "Reassign" : "Assign technician" },
        { kind: "cancel", label: "Cancel job" },
      ];
    case "SCHEDULED":
      return [
        { kind: "transition", to: "ON_THE_WAY", label: "Mark on the way" },
        { kind: "transition", to: "IN_PROGRESS", label: "Start work" },
        { kind: "assign", label: "Reassign" },
        { kind: "cancel", label: "Cancel job" },
      ];
    case "ON_THE_WAY":
      return [
        { kind: "transition", to: "IN_PROGRESS", label: "Start work" },
        { kind: "assign", label: "Reassign" },
        { kind: "cancel", label: "Cancel job" },
      ];
    case "IN_PROGRESS":
      return [
        { kind: "complete", label: "Complete job" },
        { kind: "cancel", label: "Cancel job" },
      ];
    default:
      return [];
  }
}
