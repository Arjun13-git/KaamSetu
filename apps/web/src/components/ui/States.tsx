import { AlertTriangle, Inbox } from "lucide-react";

import { friendlyMessage, type ApiFailure } from "@/lib/api/errors";
import { cn } from "@/lib/cn";
import { Card } from "./Card";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton rounded-md", className)} />;
}

export function EmptyState({
  title,
  hint,
  icon,
  className,
}: {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-1 px-4 py-8 text-center", className)}>
      <span className="mb-1 text-ink-3">{icon ?? <Inbox className="size-5" />}</span>
      <p className="text-sm font-medium text-ink-2">{title}</p>
      {hint ? <p className="max-w-sm text-sm text-ink-3">{hint}</p> : null}
    </div>
  );
}

/** A failed read or write, in plain language, with the request id a developer would ask for. */
export function ErrorPanel({ failure, title = "Could not load this" }: { failure: ApiFailure; title?: string }) {
  return (
    <Card className="border-safety-line p-6" role="alert">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-safety" />
        <div className="min-w-0">
          <p className="font-medium">{title}</p>
          <p className="mt-1 text-ink-2">{friendlyMessage(failure)}</p>
          {failure.requestId ? (
            <p className="mt-2 font-mono text-xs text-ink-3">
              {failure.code} · {failure.requestId}
            </p>
          ) : (
            <p className="mt-2 font-mono text-xs text-ink-3">{failure.code}</p>
          )}
        </div>
      </div>
    </Card>
  );
}
