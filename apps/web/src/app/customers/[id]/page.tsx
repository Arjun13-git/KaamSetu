import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, MapPin, Phone, Plus } from "lucide-react";
import { notFound } from "next/navigation";

import { AssetSection } from "@/components/customers/AssetSection";
import { Badge } from "@/components/ui/Badge";
import { buttonClass } from "@/components/ui/Button";
import { Card, SectionLabel } from "@/components/ui/Card";
import { EmptyState, ErrorPanel } from "@/components/ui/States";
import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";
import { getTimezone } from "@/lib/config";
import { applianceLabel, formatPhone, initials, plural } from "@/lib/format";
import { technicianMap, technicianNames } from "@/lib/lookups";
import { toMemory } from "@/lib/views";

export const metadata: Metadata = { title: "Customer" };

export default async function CustomerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [history, technicians] = await Promise.all([attempt(api.customerHistory(id)), technicianMap()]);
  if (!history.ok) {
    if (history.error.status === 404) notFound();
    return <ErrorPanel failure={history.error} title="This customer could not be loaded" />;
  }
  const { customer, assets, jobs, service_events: events } = history.data;
  const tz = getTimezone();
  const now = new Date();
  const names = technicianNames(technicians);

  // The appliance with the most recorded service leads: that is where Service Memory matters most.
  const eventsFor = (assetId: string) => events.filter((e) => e.asset_id === assetId);
  const ordered = [...assets].sort((a, b) => eventsFor(b.asset_id).length - eventsFor(a.asset_id).length);
  const isOpen = (status: string) => status !== "COMPLETED" && status !== "CANCELLED";
  const phone = formatPhone(customer.phone);

  return (
    <>
      <Link href="/customers" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden />
        Customers
      </Link>

      <Card className="mb-6 flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="flex min-w-0 items-center gap-4">
          <span className="grid size-14 shrink-0 place-items-center rounded-full bg-brand-tint text-lg font-semibold text-brand-strong">
            {initials(customer.name)}
          </span>
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">{customer.name}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-2">
              {phone ? (
                <span className="inline-flex items-center gap-1.5">
                  <Phone className="size-4 text-ink-3" aria-hidden />
                  {phone}
                </span>
              ) : null}
              {customer.address ? (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="size-4 text-ink-3" aria-hidden />
                  {customer.address}
                </span>
              ) : null}
            </p>
            <p className="mt-2 flex flex-wrap gap-1.5">
              <Badge>{plural(assets.length, "appliance")}</Badge>
              <Badge tone="memory">{plural(events.length, "recorded service")}</Badge>
              <Badge tone="brand">{plural(jobs.filter((j) => isOpen(j.status)).length, "open job")}</Badge>
            </p>
          </div>
        </div>
        <Link href={`/intake${customer.phone ? `?phone=${encodeURIComponent(customer.phone)}` : ""}`} className={buttonClass("primary")}>
          <Plus className="size-4" aria-hidden />
          New request
        </Link>
      </Card>

      {ordered.length === 0 ? (
        <Card>
          <EmptyState title="No appliances on file" hint="An appliance is added when a request that mentions it is confirmed." />
        </Card>
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <nav aria-label="Appliances" className="hidden lg:sticky lg:top-20 lg:block">
            <SectionLabel className="mb-2 px-2">Appliances</SectionLabel>
            <ul className="space-y-1">
              {ordered.map((asset) => (
                <li key={asset.asset_id}>
                  <a href={`#${asset.asset_id}`} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm text-ink-2 hover:bg-sunken hover:text-ink">
                    <span className="truncate">{applianceLabel(asset)}</span>
                    <span className="shrink-0 text-xs text-memory-ink">{eventsFor(asset.asset_id).length}</span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="min-w-0 space-y-10">
            {ordered.map((asset) => (
              <AssetSection
                key={asset.asset_id}
                asset={asset}
                memory={toMemory(asset.asset_id, applianceLabel(asset), eventsFor(asset.asset_id), names, tz, now)}
                openJobs={jobs.filter((j) => j.asset_id === asset.asset_id && isOpen(j.status))}
                technicianNames={names}
                tz={tz}
                now={now}
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}
