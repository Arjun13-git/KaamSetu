import { Skeleton } from "./States";

/** Shown by a route's loading.tsx the moment a link is followed, before its data arrives. */
export function DetailSkeleton() {
  return (
    <div aria-busy="true" role="status" aria-label="Loading">
      <Skeleton className="mb-4 h-5 w-24" />
      <Skeleton className="mb-2 h-6 w-40" />
      <Skeleton className="mb-2 h-9 w-2/3 max-w-xl" />
      <Skeleton className="mb-6 h-5 w-1/2 max-w-md" />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="space-y-5">
          <Skeleton className="h-36 rounded-(--radius-card)" />
          <Skeleton className="h-40 rounded-(--radius-card)" />
          <Skeleton className="h-72 rounded-(--radius-card)" />
        </div>
        <div className="space-y-5">
          <Skeleton className="h-36 rounded-(--radius-card)" />
          <Skeleton className="h-44 rounded-(--radius-card)" />
        </div>
      </div>
    </div>
  );
}

export function QueueSkeleton() {
  return (
    <div aria-busy="true" role="status" aria-label="Loading" className="mx-auto max-w-2xl">
      <Skeleton className="mb-4 h-5 w-28" />
      <Skeleton className="mb-6 h-48 rounded-(--radius-card)" />
      <Skeleton className="mb-3 h-72 rounded-(--radius-card)" />
      <Skeleton className="h-72 rounded-(--radius-card)" />
    </div>
  );
}
