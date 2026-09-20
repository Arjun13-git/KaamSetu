"use server";

import { api } from "@/lib/api/endpoints";
import { toFailure, type ApiFailure } from "@/lib/api/errors";
import { getTimezone } from "@/lib/config";
import { buildIntakeView } from "@/lib/intake-view";
import type { IntakeBody } from "@/lib/api/types";
import type { IntakeView } from "@/lib/views";

export type IntakeState =
  | { status: "idle" }
  | { status: "done"; view: IntakeView }
  | { status: "error"; failure: ApiFailure };

const MAX_PHOTO_BYTES = 3_500_000;
const PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);

function invalid(message: string, path: string): IntakeState {
  return {
    status: "error",
    failure: { code: "VALIDATION_ERROR", message, status: 422, requestId: null, fields: [{ path, message }] },
  };
}

/**
 * Sends the customer's message to the API and returns what to show. The Idempotency-Key comes from
 * the form, so submitting the same message twice (a retry, a double click) returns the same
 * result without a second job or a second model call.
 */
export async function submitIntake(_previous: IntakeState, formData: FormData): Promise<IntakeState> {
  const text = String(formData.get("text") ?? "").trim();
  const phone = String(formData.get("phone") ?? "").trim() || null;
  const key = String(formData.get("key") ?? "").trim();
  const photo = formData.get("photo");

  if (!text) return invalid("Type or paste the customer's message.", "text");
  if (text.length > 4000) return invalid("That message is too long (4000 characters at most).", "text");
  if (!/^[A-Za-z0-9_-]{8,128}$/.test(key)) return invalid("The form is out of date. Reload the page.", "key");

  const body: IntakeBody & { image?: { media_type: string; data_base64: string } } = { text, phone };
  if (photo instanceof File && photo.size > 0) {
    if (!PHOTO_TYPES.has(photo.type)) return invalid("The photo must be a JPEG, PNG, WebP or GIF.", "photo");
    if (photo.size > MAX_PHOTO_BYTES) return invalid("The photo is too large (3.5 MB at most).", "photo");
    body.image = {
      media_type: photo.type,
      data_base64: Buffer.from(await photo.arrayBuffer()).toString("base64"),
    };
  }

  try {
    const result = await api.intake(body, key);
    return { status: "done", view: await buildIntakeView(result, { phone }, getTimezone(), new Date()) };
  } catch (error) {
    return { status: "error", failure: toFailure(error) };
  }
}
