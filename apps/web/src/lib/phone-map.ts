// The API does not store the phone number an operator typed at intake, so the review flow would
// lose it. The app remembers it, per request, in a small cookie (see phone-memory.ts). This is the
// pure part: parsing and updating the remembered map, bounded so the cookie stays small.

export type PhoneMap = Record<string, string>;

const MAX_ENTRIES = 12;
const ID = /^[A-Za-z0-9_-]{3,80}$/;
const PHONE = /^[+\d][\d ()+-]{3,24}$/;

export function parsePhoneMap(raw: string | undefined | null): PhoneMap {
  if (!raw) return {};
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null || Array.isArray(value)) return {};
    const map: PhoneMap = {};
    for (const [id, phone] of Object.entries(value)) {
      if (ID.test(id) && typeof phone === "string" && PHONE.test(phone)) map[id] = phone;
    }
    return map;
  } catch {
    return {};
  }
}

/** Adds one entry, dropping the oldest ones beyond the limit. Invalid input leaves the map as it was. */
export function rememberPhoneIn(map: PhoneMap, requestId: string, phone: string): PhoneMap {
  const trimmed = phone.trim();
  if (!ID.test(requestId) || !PHONE.test(trimmed)) return map;
  const { [requestId]: _replaced, ...rest } = map;
  void _replaced;
  const entries = [...Object.entries(rest), [requestId, trimmed] as const];
  return Object.fromEntries(entries.slice(-MAX_ENTRIES));
}

/** A phone number as the review form should carry it: only what looks like a phone number. */
export function cleanPhone(value: string | undefined | null): string {
  const trimmed = (value ?? "").trim();
  return PHONE.test(trimmed) ? trimmed : "";
}
