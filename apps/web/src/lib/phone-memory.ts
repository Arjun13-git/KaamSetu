import "server-only";

import { cookies, headers } from "next/headers";

import { parsePhoneMap, rememberPhoneIn } from "./phone-map";

const COOKIE = "ks_intake_phones";
const SEVEN_DAYS = 60 * 60 * 24 * 7;

/** Remember the phone typed at intake for this request, in the operator's own browser (httpOnly). */
export async function rememberPhone(requestId: string, phone: string | null): Promise<void> {
  if (!phone) return;
  const jar = await cookies();
  const current = parsePhoneMap(jar.get(COOKIE)?.value);
  const next = rememberPhoneIn(current, requestId, phone);
  if (next === current) return;
  const proto = (await headers()).get("x-forwarded-proto");
  jar.set(COOKIE, JSON.stringify(next), {
    httpOnly: true,
    sameSite: "lax",
    secure: proto === "https",
    path: "/",
    maxAge: SEVEN_DAYS,
  });
}

export async function recallPhone(requestId: string): Promise<string> {
  const jar = await cookies();
  return parsePhoneMap(jar.get(COOKIE)?.value)[requestId] ?? "";
}
