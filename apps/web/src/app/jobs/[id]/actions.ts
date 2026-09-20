"use server";

import { api } from "@/lib/api/endpoints";
import { toFailure, type ApiFailure } from "@/lib/api/errors";
import { getTimezone } from "@/lib/config";
import { zonedToUtc } from "@/lib/format";

export type ActionResult = { ok: true } | { ok: false; failure: ApiFailure };

const ID = /^[A-Za-z0-9_-]{3,80}$/;

function rejected(message: string, path = ""): ActionResult {
  return { ok: false, failure: { code: "VALIDATION_ERROR", message, status: 422, requestId: null, fields: path ? [{ path, message }] : [] } };
}

async function run(work: () => Promise<unknown>): Promise<ActionResult> {
  try {
    await work();
    return { ok: true };
  } catch (error) {
    return { ok: false, failure: toFailure(error) };
  }
}

// The API decides every rule (who is active, which move is legal, what completion needs). These
// actions only check the shape of what a form sent, relay it, and report the API's answer.

export async function assignJobAction(jobId: string, technicianId: string): Promise<ActionResult> {
  if (!ID.test(jobId) || !ID.test(technicianId)) return rejected("Choose a technician.", "technician");
  return run(() => api.assignJob(jobId, technicianId));
}

export async function transitionJobAction(jobId: string, to: "ON_THE_WAY" | "IN_PROGRESS" | "CANCELLED"): Promise<ActionResult> {
  if (!ID.test(jobId)) return rejected("Unknown job.");
  if (to !== "ON_THE_WAY" && to !== "IN_PROGRESS" && to !== "CANCELLED") return rejected("That move is not available here.");
  return run(() => api.transitionJob(jobId, { to_status: to }));
}

export async function scheduleJobAction(jobId: string, localDateTime: string): Promise<ActionResult> {
  if (!ID.test(jobId)) return rejected("Unknown job.");
  const start = zonedToUtc(localDateTime, getTimezone());
  if (!start) return rejected("Pick a date and time for the visit.", "slot");
  return run(() => api.transitionJob(jobId, { to_status: "SCHEDULED", scheduled_slot: { start } }));
}

export interface CompletionInput {
  workPerformed: string;
  notes: string;
  parts: string;
  symptoms: string;
  followUp: boolean;
}

function list(text: string): string[] {
  return text
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 20);
}

export async function completeJobAction(jobId: string, input: CompletionInput): Promise<ActionResult> {
  if (!ID.test(jobId)) return rejected("Unknown job.");
  const work = input.workPerformed.trim();
  if (!work) return rejected("Describe the work that was done.", "work_performed");
  return run(() =>
    api.completeJob(jobId, {
      work_performed: work,
      technician_notes: input.notes.trim() || null,
      parts_used: list(input.parts),
      observed_symptoms: list(input.symptoms),
      follow_up_required: input.followUp,
    }),
  );
}
