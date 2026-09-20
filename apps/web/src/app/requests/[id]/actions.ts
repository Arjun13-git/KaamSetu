"use server";

import { redirect } from "next/navigation";

import { api } from "@/lib/api/endpoints";
import { toFailure, type ApiFailure } from "@/lib/api/errors";
import type { AssetType, ConfirmJobBody, ServiceType, Urgency } from "@/lib/api/types";
import { getTimezone } from "@/lib/config";
import { zonedToUtc } from "@/lib/format";
import { cleanPhone } from "@/lib/phone-map";
import { ASSET_TYPE_OPTIONS, ENTITY_ID, SERVICE_TYPE_OPTIONS, URGENCY_OPTIONS, reviewUrl } from "@/lib/review";

/** `values` echoes what was typed, so a refused form keeps its contents instead of resetting. */
export type ReviewFormState =
  | { status: "idle" }
  | { status: "error"; failure: ApiFailure; values: Record<string, string> }
  | { status: "duplicate"; customers: Array<{ id: string; name: string; phone: string | null }>; values: Record<string, string> };

// Each step of the review commits on its own and the person sees the result before the next one.
// That keeps a retry from creating a second customer or appliance, and the API stays the authority
// on every rule: these actions check the shape of a form, relay it, and report the API's answer.

const text = (data: FormData, key: string) => String(data.get(key) ?? "").trim();

function valuesOf(data: FormData): Record<string, string> {
  const values: Record<string, string> = {};
  for (const [key, value] of data.entries()) if (typeof value === "string" && !key.startsWith("$ACTION")) values[key] = value;
  return values;
}

function refuse(data: FormData, message: string, path: string): ReviewFormState {
  return {
    status: "error",
    values: valuesOf(data),
    failure: { code: "VALIDATION_ERROR", message, status: 422, requestId: null, fields: [{ path, message }] },
  };
}

export async function createCustomerAction(_previous: ReviewFormState, data: FormData): Promise<ReviewFormState> {
  const requestId = text(data, "requestId");
  const name = text(data, "name");
  const phone = cleanPhone(text(data, "phone"));
  const address = text(data, "address");
  if (!ENTITY_ID.test(requestId)) return refuse(data, "This request is not valid.", "requestId");
  if (!name) return refuse(data, "Enter the customer's name.", "name");
  if (text(data, "phone") && !phone) return refuse(data, "That does not look like a phone number.", "phone");

  let customerId: string;
  try {
    // A phone number identifies a customer. Creating a second one would make every future message
    // from that number ambiguous, so an existing owner is offered instead.
    if (phone) {
      const existing = await api.customers({ phone });
      if (existing.length > 0) {
        return { status: "duplicate", values: valuesOf(data), customers: existing.map((c) => ({ id: c.customer_id, name: c.name, phone: c.phone })) };
      }
    }
    customerId = (await api.createCustomer({ name, phone: phone || null, address: address || null })).customer_id;
  } catch (error) {
    return { status: "error", values: valuesOf(data), failure: toFailure(error) };
  }
  redirect(reviewUrl(requestId, { customer: customerId, phone }));
}

export async function createAssetAction(_previous: ReviewFormState, data: FormData): Promise<ReviewFormState> {
  const requestId = text(data, "requestId");
  const customerId = text(data, "customerId");
  const assetType = text(data, "assetType");
  const phone = cleanPhone(text(data, "phone"));
  if (!ENTITY_ID.test(requestId) || !ENTITY_ID.test(customerId)) return refuse(data, "This request is not valid.", "requestId");
  if (!ASSET_TYPE_OPTIONS.some((option) => option.value === assetType)) return refuse(data, "Choose the kind of appliance.", "assetType");

  let assetId: string;
  try {
    const created = await api.createAsset(customerId, {
      asset_type: assetType as AssetType,
      brand: text(data, "brand") || null,
      model: text(data, "model") || null,
      location: text(data, "location") || null,
    });
    assetId = created.asset_id;
  } catch (error) {
    return { status: "error", values: valuesOf(data), failure: toFailure(error) };
  }
  redirect(reviewUrl(requestId, { customer: customerId, asset: assetId, phone }));
}

export async function confirmJobAction(_previous: ReviewFormState, data: FormData): Promise<ReviewFormState> {
  const requestId = text(data, "requestId");
  const customerId = text(data, "customerId");
  const assetId = text(data, "assetId");
  if (!ENTITY_ID.test(requestId) || !ENTITY_ID.test(customerId) || !ENTITY_ID.test(assetId)) {
    return refuse(data, "Choose a customer and an appliance first.", "requestId");
  }

  // Only what the person changed is sent; everything else stays the API's own proposal.
  const body: ConfirmJobBody = { customer_id: customerId, asset_id: assetId };
  const description = text(data, "description");
  if (!description) return refuse(data, "Describe the job.", "description");
  if (description !== text(data, "descriptionDefault")) body.description = description;

  const serviceType = text(data, "serviceType");
  if (serviceType) {
    if (!(SERVICE_TYPE_OPTIONS as readonly string[]).includes(serviceType)) return refuse(data, "Unknown type of work.", "serviceType");
    body.service_type = serviceType as ServiceType;
  }
  const urgency = text(data, "urgency");
  if (urgency) {
    if (!(URGENCY_OPTIONS as readonly string[]).includes(urgency)) return refuse(data, "Unknown urgency.", "urgency");
    body.urgency = urgency as Urgency;
  }
  const visit = text(data, "visit");
  if (visit && visit !== text(data, "visitDefault")) {
    const start = zonedToUtc(visit, getTimezone());
    if (!start) return refuse(data, "Pick a valid date and time.", "visit");
    body.preferred_slot = { start };
  }

  let jobId: string;
  try {
    jobId = (await api.confirmRequest(requestId, body)).job_id;
  } catch (error) {
    return { status: "error", values: valuesOf(data), failure: toFailure(error) };
  }
  redirect(`/jobs/${jobId}`);
}
