import "server-only";

import { api } from "./api/endpoints";
import { attempt } from "./api/errors";
import type { Asset, Customer, Technician } from "./api/types";

// The API's lists carry ids, not names, and it has no "expand" option. These helpers resolve the
// names a screen needs from the (briefly cached) lookups, and degrade to "unknown" rather than
// failing the page when a lookup is unavailable.

export async function technicianMap(): Promise<Map<string, Technician>> {
  const result = await attempt(api.technicians());
  return new Map((result.ok ? result.data : []).map((t) => [t.technician_id, t]));
}

export async function customerMap(): Promise<Map<string, Customer>> {
  const result = await attempt(api.customers({ limit: 100 }));
  return new Map((result.ok ? result.data : []).map((c) => [c.customer_id, c]));
}

/** Assets of the given customers, fetched in parallel (the API has no "list all assets"). */
export async function assetMap(customerIds: string[]): Promise<Map<string, Asset>> {
  const unique = [...new Set(customerIds)];
  const lists = await Promise.all(unique.map((id) => attempt(api.customerAssets(id))));
  const map = new Map<string, Asset>();
  for (const list of lists) {
    if (list.ok) for (const asset of list.data) map.set(asset.asset_id, asset);
  }
  return map;
}

export function technicianNames(technicians: Map<string, Technician>): Map<string, string> {
  return new Map([...technicians].map(([id, t]) => [id, t.name]));
}
