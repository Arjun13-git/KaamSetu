import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";

/** Live proof that the UI is talking to the deployed service, not to mock data. */
export async function ApiStatusPill() {
  const result = await attempt(api.health());
  if (!result.ok) {
    return (
      <span
        className="hidden items-center gap-2 rounded-full border border-safety-line bg-safety-tint px-3 py-1 text-xs text-safety-strong md:inline-flex"
        title={result.error.message}
      >
        <span className="size-2 rounded-full bg-safety" />
        API unreachable
      </span>
    );
  }
  return (
    <span
      className="hidden items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-ink-2 md:inline-flex"
      title={`KaamSetu API v${result.data.version}`}
    >
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full rounded-full bg-ok opacity-40 motion-safe:animate-ping" />
        <span className="relative inline-flex size-2 rounded-full bg-ok" />
      </span>
      Live · API v{result.data.version}
    </span>
  );
}
