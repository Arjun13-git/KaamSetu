import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight, Search } from "lucide-react";
import { Suspense } from "react";

import { Button } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/Card";
import { EmptyState, ErrorPanel, Skeleton } from "@/components/ui/States";
import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";
import { formatPhone, initials, plural } from "@/lib/format";

export const metadata: Metadata = { title: "Customers" };

async function CustomerList({ query }: { query: string }) {
  const [customers, jobs] = await Promise.all([attempt(api.customers({ q: query || undefined })), attempt(api.jobs({ limit: 200 }))]);
  if (!customers.ok) return <ErrorPanel failure={customers.error} title="Customers could not be loaded" level={2} />;

  const open = new Map<string, number>();
  const served = new Map<string, number>();
  for (const job of jobs.ok ? jobs.data : []) {
    const target = job.status === "COMPLETED" ? served : job.status === "CANCELLED" ? null : open;
    if (target) target.set(job.customer_id, (target.get(job.customer_id) ?? 0) + 1);
  }

  if (customers.data.length === 0) {
    return (
      <Card>
        <EmptyState title={query ? `No customer matches “${query}”` : "No customers yet"} hint="Customers are created when a request from a new person is confirmed." />
      </Card>
    );
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {customers.data.map((customer) => (
        <li key={customer.customer_id}>
          <Link
            href={`/customers/${customer.customer_id}`}
            className="flex h-full items-center gap-3 rounded-(--radius-card) border border-line bg-surface p-4 shadow-card transition-shadow hover:shadow-pop"
          >
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-brand-tint text-sm font-semibold text-brand-strong">
              {initials(customer.name)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{customer.name}</p>
              <p className="truncate text-sm text-ink-2">{formatPhone(customer.phone) ?? "No phone"}</p>
              <p className="mt-1 text-xs text-ink-3">
                {plural(open.get(customer.customer_id) ?? 0, "open job")} · {plural(served.get(customer.customer_id) ?? 0, "completed job")}
              </p>
            </div>
            <ChevronRight className="size-4 shrink-0 text-ink-3" aria-hidden />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default async function CustomersPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q } = await searchParams;
  const query = (q ?? "").trim().slice(0, 100);
  return (
    <>
      <PageHeader title="Customers" subtitle="Every appliance keeps its own service memory." />
      <form action="/customers" role="search" className="mb-5 flex max-w-md gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <input
            name="q"
            defaultValue={query}
            placeholder="Search by name"
            aria-label="Search customers by name"
            className="h-10 w-full rounded-lg border border-line-strong bg-surface pr-3 pl-9 text-sm placeholder:text-ink-3 focus:border-brand"
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>
      <Suspense key={query} fallback={<Skeleton className="h-64" />}>
        <CustomerList query={query} />
      </Suspense>
    </>
  );
}
