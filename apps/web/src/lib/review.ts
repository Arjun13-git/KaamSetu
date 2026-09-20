// Defaults for the review forms, read from the AI extraction and the customer's own words. They only
// pre-fill fields a person can change; nothing here decides anything, and unknown stays empty.

import type { ParsedExtraction } from "./extraction.ts";

const MAX_DESCRIPTION = 2000;

export interface JobFormDefaults {
  description: string;
  /** The customer's requested visit as a datetime-local value, only when both date and time were given. */
  visitInput: string;
}

export function jobFormDefaults(extraction: ParsedExtraction | null, rawText: string): JobFormDefaults {
  const described = extraction?.data.problem.description ?? null;
  const description = described ?? (rawText.length <= MAX_DESCRIPTION ? rawText : "");
  const time = extraction?.data.timePreference;
  const visitInput = time?.date && time.start ? `${time.date}T${time.start.slice(0, 5)}` : "";
  return { description, visitInput };
}

export function customerFormDefaults(extraction: ParsedExtraction | null): { name: string } {
  return { name: extraction?.data.customerReference ?? "" };
}

export interface AssetFormDefaults {
  assetType: string;
  brand: string;
  model: string;
}

export function assetFormDefaults(extraction: ParsedExtraction | null): AssetFormDefaults {
  const asset = extraction?.data.asset;
  return {
    assetType: asset && asset.type !== "unknown" ? asset.type : "",
    brand: asset?.brand ?? "",
    model: asset?.model ?? "",
  };
}

export const ASSET_TYPE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "air_conditioner", label: "Air conditioner" },
  { value: "refrigerator", label: "Refrigerator" },
  { value: "washing_machine", label: "Washing machine" },
  { value: "microwave", label: "Microwave" },
  { value: "television", label: "Television" },
  { value: "water_purifier", label: "Water purifier" },
  { value: "computer", label: "Computer" },
  { value: "printer", label: "Printer" },
  { value: "electrical", label: "Electrical" },
  { value: "plumbing", label: "Plumbing" },
  { value: "other", label: "Other" },
];

export const SERVICE_TYPE_OPTIONS = ["repair", "installation", "maintenance", "inspection", "replacement", "unknown"] as const;
export const URGENCY_OPTIONS = ["low", "normal", "high", "safety_critical"] as const;

export interface ReviewLocation {
  customer?: string | null;
  asset?: string | null;
  phone?: string | null;
  q?: string | null;
  change?: "customer" | "asset" | null;
}

/** The URL of a review step. Everything the flow needs is in it, so it survives a reload or Back. */
export function reviewUrl(requestId: string, where: ReviewLocation = {}): string {
  const params = new URLSearchParams();
  for (const key of ["customer", "asset", "phone", "q", "change"] as const) {
    const value = where[key];
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return `/requests/${requestId}${query ? `?${query}` : ""}`;
}

export const ENTITY_ID = /^[A-Za-z0-9_-]{3,80}$/;
