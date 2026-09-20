import "server-only";

import { getConfig } from "@/lib/config";
import { cached, clearCache, createLimiter } from "./cache";
import { ApiError, NETWORK, TIMEOUT, failureFromBody } from "./errors";

type Query = Record<string, string | number | boolean | null | undefined>;

interface RequestOptions {
  query?: Query;
  body?: unknown;
  headers?: Record<string, string>;
  /** Reads only: reuse an identical read made within this many milliseconds. */
  ttlMs?: number;
  timeoutMs?: number;
}

const limit = createLimiter(6);
const RETRYABLE = new Set([429, 502, 503, 504]);

function buildUrl(base: string, path: string, query?: Query): string {
  const url = new URL(`${base}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }
  return url.toString();
}

function cacheKey(path: string, query?: Query): string {
  const entries = Object.entries(query ?? {}).filter(([, v]) => v !== null && v !== undefined && v !== "");
  return `${path}?${entries.map(([k, v]) => `${k}=${String(v)}`).sort().join("&")}`;
}

async function send<T>(method: string, path: string, options: RequestOptions): Promise<T> {
  const config = getConfig();
  const url = buildUrl(config.apiUrl, path, options.query);
  const headers: Record<string, string> = { Accept: "application/json", ...options.headers };
  if (config.demoKey) headers["X-Demo-Key"] = config.demoKey;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const attempts = method === "GET" ? 2 : 1;
  for (let attempt = 1; ; attempt += 1) {
    let response: Response;
    try {
      response = await limit(() =>
        fetch(url, {
          method,
          headers,
          body: options.body === undefined ? undefined : JSON.stringify(options.body),
          cache: "no-store",
          signal: AbortSignal.timeout(options.timeoutMs ?? 20_000),
        }),
      );
    } catch (cause) {
      const timedOut = cause instanceof Error && (cause.name === "TimeoutError" || cause.name === "AbortError");
      if (attempt < attempts) continue;
      throw new ApiError({
        code: timedOut ? TIMEOUT : NETWORK,
        message: timedOut ? "The API did not answer in time" : "The API could not be reached",
        status: 0,
        requestId: null,
        fields: [],
      });
    }

    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (response.ok) return (body as { data: T }).data;
    if (attempt < attempts && RETRYABLE.has(response.status)) {
      await new Promise((resume) => setTimeout(resume, 350));
      continue;
    }
    throw new ApiError(failureFromBody(response.status, body, response.headers.get("x-request-id")));
  }
}

export function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const load = () => send<T>("GET", path, options);
  if (!options.ttlMs) return load();
  return cached(cacheKey(path, options.query), options.ttlMs, load);
}

/** Every write clears the read cache, so the page that follows never shows a stale record. */
export async function apiWrite<T>(
  method: "POST" | "PATCH",
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  try {
    return await send<T>(method, path, options);
  } finally {
    clearCache();
  }
}
