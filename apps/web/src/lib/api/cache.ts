// A tiny in-process cache for API reads. It exists for two reasons: a page shows several things
// that need the same lookup (a customer's name on ten job cards), and the deployed API is throttled
// at 10 requests per second. Concurrent identical reads share one call; results live for a few
// seconds; any write clears everything so the next read is fresh.

interface Entry {
  expires: number;
  value: Promise<unknown>;
}

const store = new Map<string, Entry>();

export function cached<T>(key: string, ttlMs: number, load: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const hit = store.get(key);
  if (hit && hit.expires > now) return hit.value as Promise<T>;
  const value = load().catch((error: unknown) => {
    store.delete(key);
    throw error;
  });
  store.set(key, { expires: now + ttlMs, value });
  return value;
}

export function clearCache(): void {
  store.clear();
}

/** Run at most `limit` tasks at once (a plain semaphore) so a page never bursts the API. */
export function createLimiter(limit: number) {
  let active = 0;
  const waiting: Array<() => void> = [];
  return async function run<T>(task: () => Promise<T>): Promise<T> {
    if (active >= limit) {
      await new Promise<void>((resume) => waiting.push(resume)); // the slot is handed over
    } else {
      active += 1;
    }
    try {
      return await task();
    } finally {
      const next = waiting.shift();
      if (next) next();
      else active -= 1;
    }
  };
}
