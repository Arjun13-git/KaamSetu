import "server-only";

import { api } from "./api/endpoints";
import { attempt } from "./api/errors";
import type { Asset, Customer, EntityResolution, IntakeResult } from "./api/types";
import { applianceLabel, formatPhone, formatSlot, describeTimePreference } from "./format";
import { parseExtraction } from "./extraction";
import { technicianMap, technicianNames } from "./lookups";
import {
  reviewReasons,
  toMemory,
  understoodAs,
  type CandidateView,
  type IntakeView,
  type ResolutionView,
} from "./views";

function customerDetail(customer: Customer): string | null {
  return [formatPhone(customer.phone), customer.address].filter(Boolean).join(" · ") || null;
}

function assetTitle(asset: Asset): string {
  return applianceLabel(asset);
}

function assetDetail(asset: Asset): string | null {
  return [asset.model ? `Model ${asset.model}` : null, asset.location].filter(Boolean).join(" · ") || null;
}

function baseView(kind: "customer" | "asset", resolution: EntityResolution): ResolutionView {
  const chosen = resolution.candidates.find((c) => c.entity_id === resolution.entity_id);
  return {
    kind,
    state: resolution.state,
    title: "",
    detail: null,
    reasons: chosen?.reasons ?? [],
    score: chosen?.match_score ?? null,
    href: null,
    candidates: [],
  };
}

/**
 * Turns the API's intake answer into what the five-stage result renders. It adds names (the API
 * returns ids) and formats times in the business timezone; it decides nothing about the request.
 */
export async function buildIntakeView(
  result: IntakeResult,
  input: { phone: string | null },
  tz: string,
  now: Date,
): Promise<IntakeView> {
  const request = result.service_request;
  const customerRes = request.customer_resolution;
  const assetRes = request.asset_resolution;
  const extraction = parseExtraction(request.extraction);

  const customerIds = customerRes.entity_id
    ? [customerRes.entity_id]
    : customerRes.candidates.map((c) => c.entity_id);
  const [customerLookups, assetLookup, technicians] = await Promise.all([
    Promise.all(customerIds.map((id) => attempt(api.customer(id)))),
    customerRes.entity_id ? attempt(api.customerAssets(customerRes.entity_id)) : Promise.resolve(null),
    technicianMap(),
  ]);
  const customers = new Map<string, Customer>();
  for (const lookup of customerLookups) if (lookup.ok) customers.set(lookup.data.customer_id, lookup.data);
  const assets = new Map<string, Asset>();
  if (assetLookup?.ok) for (const asset of assetLookup.data) assets.set(asset.asset_id, asset);

  // -- customer -----------------------------------------------------------------------------
  const customer = baseView("customer", customerRes);
  if (customerRes.state === "existing" && customerRes.entity_id) {
    const found = customers.get(customerRes.entity_id);
    customer.title = found?.name ?? "Existing customer";
    customer.detail = found ? customerDetail(found) : null;
    customer.href = `/customers/${customerRes.entity_id}`;
  } else if (customerRes.state === "ambiguous") {
    customer.title = `${customerRes.candidates.length} customers could match`;
    customer.detail = "A name alone is not enough to be sure. A person confirms which one.";
    customer.candidates = customerRes.candidates.map(
      (c): CandidateView => ({
        id: c.entity_id,
        title: customers.get(c.entity_id)?.name ?? c.entity_id,
        detail: customers.get(c.entity_id) ? customerDetail(customers.get(c.entity_id)!) : null,
        score: c.match_score,
        reasons: c.reasons,
        href: `/customers/${c.entity_id}`,
      }),
    );
  } else if (customerRes.state === "new") {
    customer.title = "New customer";
    customer.detail = "Nobody on file matches this phone number or name.";
  } else {
    customer.title = "Not identified";
    customer.detail = input.phone ? "The phone number did not match anyone." : "No phone number was given.";
  }

  // -- asset --------------------------------------------------------------------------------
  const asset = baseView("asset", assetRes);
  if (assetRes.state === "existing" && assetRes.entity_id) {
    const found = assets.get(assetRes.entity_id);
    asset.title = found ? assetTitle(found) : "Existing appliance";
    asset.detail = found ? assetDetail(found) : null;
    asset.href = customerRes.entity_id ? `/customers/${customerRes.entity_id}#${assetRes.entity_id}` : null;
  } else if (assetRes.state === "ambiguous") {
    asset.title = `${assetRes.candidates.length} appliances could match`;
    asset.detail = "The message fits more than one of this customer's appliances.";
    asset.candidates = assetRes.candidates.map((c): CandidateView => {
      const found = assets.get(c.entity_id);
      return {
        id: c.entity_id,
        title: found ? assetTitle(found) : c.entity_id,
        detail: found ? assetDetail(found) : null,
        score: c.match_score,
        reasons: c.reasons,
        href: null,
      };
    });
  } else if (assetRes.state === "new") {
    asset.title = "New appliance";
    asset.detail = "Not on file for this customer.";
  } else {
    asset.title = "Not identified";
    asset.detail = customerRes.state === "existing" ? "The message did not say which appliance." : "Waiting for the customer to be confirmed.";
  }

  // -- service memory: only for an appliance that was positively identified --------------------
  const memory =
    assetRes.state === "existing" && assetRes.entity_id
      ? toMemory(
          assetRes.entity_id,
          assets.get(assetRes.entity_id) ? assetTitle(assets.get(assetRes.entity_id)!) : "this appliance",
          result.prior_service,
          technicianNames(technicians),
          tz,
          now,
        )
      : null;

  return {
    outcome: result.outcome,
    serviceRequestId: request.service_request_id,
    safety: result.safety_concern,
    rawText: request.raw_text,
    phone: input.phone,
    understoodAs: understoodAs(extraction, tz, now),
    customer,
    asset,
    memory,
    understanding: extraction
      ? { extraction, timeLabel: describeTimePreference(extraction.data.timePreference, tz, now) }
      : null,
    job: result.job
      ? {
          id: result.job.job_id,
          description: result.job.description,
          status: result.job.status,
          urgency: result.job.urgency,
          slotLabel: formatSlot(result.job.preferred_slot, tz, now),
          href: `/jobs/${result.job.job_id}`,
        }
      : null,
    reviewReasons: reviewReasons(result.outcome, customerRes.state, assetRes.state),
    failureReason: request.failure_reason,
  };
}
