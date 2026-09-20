import { Suspense } from "react";

import { AutoRefresh } from "@/components/board/AutoRefresh";
import { FinishedLane } from "@/components/board/FinishedLane";
import { NeedsAttention } from "@/components/board/NeedsAttention";
import { StatusColumn } from "@/components/board/StatusColumn";
import { TechnicianFilter } from "@/components/board/TechnicianFilter";
import { LinkButton } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/Card";
import { ErrorPanel, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";
import { buildBoard } from "@/lib/board";
import { getTimezone } from "@/lib/config";
import { assetMap, customerMap, technicianMap } from "@/lib/lookups";
import { plural } from "@/lib/format";

export const metadata = { title: "Job board" };

async function Board({ technicianId }: { technicianId: string | null }) {
  const jobs = await attempt(api.jobs({ limit: 200 }));
  if (!jobs.ok) return <ErrorPanel failure={jobs.error} title="The board could not be loaded" />;

  // Names come from cached lookups; assets are fetched only for customers who have open work, so a
  // board load stays at a handful of calls well inside the API's throttle.
  const openCustomers = jobs.data
    .filter((j) => j.status !== "COMPLETED" && j.status !== "CANCELLED")
    .map((j) => j.customer_id);
  const [customers, technicians, assets, needsReview, failed] = await Promise.all([
    customerMap(),
    technicianMap(),
    assetMap(openCustomers),
    attempt(api.serviceRequests({ status: "NEEDS_REVIEW" })),
    attempt(api.serviceRequests({ status: "EXTRACTION_FAILED" })),
  ]);

  const board = buildBoard(
    jobs.data,
    [...(needsReview.ok ? needsReview.data : []), ...(failed.ok ? failed.data : [])],
    { customers, assets, technicians },
    { technicianId, tz: getTimezone(), now: new Date() },
  );

  return (
    <>
      <PageHeader
        title="Job board"
        subtitle={`${plural(board.openCount, "open job")} · ${board.attention.review.length} waiting for review`}
        actions={
          <>
            <AutoRefresh />
            <LinkButton href="/intake" variant="secondary">
              New request
            </LinkButton>
          </>
        }
      />
      <NeedsAttention attention={board.attention} />
      <div className="mb-4">
        <TechnicianFilter technicians={[...technicians.values()]} selected={technicianId} />
      </div>
      <div className="grid gap-3 md:grid-flow-col md:auto-cols-[minmax(250px,1fr)] md:overflow-x-auto md:pb-2 xl:grid-flow-row xl:grid-cols-5 xl:overflow-visible">
        {board.columns.map((column) => (
          <StatusColumn key={column.status} status={column.status} cards={column.cards} />
        ))}
      </div>
      <FinishedLane finished={board.finished} />
    </>
  );
}

function BoardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the board">
      <Skeleton className="mb-2 h-8 w-48" />
      <Skeleton className="mb-6 h-5 w-64" />
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-72 rounded-(--radius-card)" />
        ))}
      </div>
    </div>
  );
}

export default async function BoardPage({ searchParams }: { searchParams: Promise<{ tech?: string }> }) {
  const { tech } = await searchParams;
  return (
    <Suspense key={tech ?? "all"} fallback={<BoardSkeleton />}>
      <Board technicianId={tech ?? null} />
    </Suspense>
  );
}
