"use client";

import { RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { Button } from "@/components/ui/Button";

const INTERVAL_MS = 20_000;

/**
 * Re-reads the page's data while the tab is visible. The API is throttled and has no push channel,
 * so this is a slow, polite poll, and it pauses in the background.
 */
export function AutoRefresh() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState !== "visible") return;
      startTransition(() => {
        router.refresh();
        setUpdatedAt(new Date());
      });
    };
    const timer = window.setInterval(refresh, INTERVAL_MS);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [router]);

  return (
    <div className="flex items-center gap-2 text-xs text-ink-3">
      <span className="hidden sm:inline">
        {updatedAt
          ? `Updated ${updatedAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" })}`
          : "Refreshes every 20 s"}
      </span>
      <Button
        variant="ghost"
        size="sm"
        className="max-sm:h-10 max-sm:px-3"
        aria-label="Refresh the board"
        onClick={() =>
          startTransition(() => {
            router.refresh();
            setUpdatedAt(new Date());
          })
        }
      >
        <RefreshCw className={pending ? "size-4 motion-safe:animate-spin" : "size-4"} aria-hidden />
        <span className="hidden sm:inline">Refresh</span>
      </Button>
    </div>
  );
}
