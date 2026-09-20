import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Search } from "lucide-react";
import { notFound } from "next/navigation";

import { ServiceMemoryRail } from "@/components/memory/ServiceMemoryRail";
import { CandidateList } from "@/components/review/CandidateList";
import { ConfirmJobForm, NewAssetForm, NewCustomerForm } from "@/components/review/ReviewForms";
import { RequestContext } from "@/components/review/RequestContext";
import { ReviewStep } from "@/components/review/ReviewStep";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Card, PageHeader } from "@/components/ui/Card";
import { inputClass } from "@/components/ui/Field";
import { ErrorPanel } from "@/components/ui/States";
import { api } from "@/lib/api/endpoints";
import { attempt } from "@/lib/api/errors";
import type { Asset, Customer } from "@/lib/api/types";
import { getTimezone } from "@/lib/config";
import { describeTimePreference, applianceLabel, formatDateTime, formatPhone } from "@/lib/format";
import { parseExtraction } from "@/lib/extraction";
import { technicianMap, technicianNames } from "@/lib/lookups";
import { cleanPhone } from "@/lib/phone-map";
import { recallPhone } from "@/lib/phone-memory";
import { ENTITY_ID, assetFormDefaults, customerFormDefaults, jobFormDefaults, reviewUrl } from "@/lib/review";
import { provenance, toMemory, understoodAs, type CandidateView } from "@/lib/views";

export const metadata: Metadata = { title: "Review request" };

type Search = { customer?: string; asset?: string; phone?: string; q?: string; change?: string };

const customerDetail = (c: Customer) => [formatPhone(c.phone), c.address].filter(Boolean).join(" · ") || null;
const assetDetail = (a: Asset) => [a.model ? `Model ${a.model}` : null, a.location].filter(Boolean).join(" · ") || null;

function AlreadyHandled({ status, jobId }: { status: string; jobId: string | null }) {
  return (
    <Card className="mx-auto max-w-lg p-6 text-center">
      <p className="font-semibold">{jobId ? "This request already became a job." : status === "DISMISSED" ? "This request was dismissed." : "This request needs no review."}</p>
      <p className="mt-1 text-sm text-ink-2">Nothing more to decide here.</p>
      <div className="mt-4 flex justify-center gap-2">
        {jobId ? (
          <Link href={`/jobs/${jobId}`} className={buttonClass("primary")}>
            Open the job
          </Link>
        ) : null}
        <Link href="/" className={buttonClass("secondary")}>
          Back to the board
        </Link>
      </div>
    </Card>
  );
}

export default async function ReviewPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<Search> }) {
  const { id } = await params;
  const sp = await searchParams;
  if (!ENTITY_ID.test(id)) notFound();

  const found = await attempt(api.serviceRequest(id));
  if (!found.ok) {
    if (found.error.status === 404) notFound();
    return <ErrorPanel failure={found.error} title="This request could not be loaded" />;
  }
  const request = found.data;
  if (request.job_id || request.status === "DISMISSED" || request.status === "JOB_CREATED") {
    return <AlreadyHandled status={request.status} jobId={request.job_id} />;
  }

  const tz = getTimezone();
  const now = new Date();
  const extraction = parseExtraction(request.extraction);
  const phone = cleanPhone(sp.phone) || (await recallPhone(id));
  const cr = request.customer_resolution;
  const ar = request.asset_resolution;
  const safety = extraction?.safetyConcern === true;

  // -- who: chosen explicitly (?customer=), or the one KaamSetu matched from evidence -------------
  const chosenParam = ENTITY_ID.test(sp.customer ?? "") ? (sp.customer as string) : null;
  const autoCustomer = sp.change !== "customer" && cr.state === "existing" ? cr.entity_id : null;
  const customerLookup = chosenParam ?? autoCustomer ? await attempt(api.customer((chosenParam ?? autoCustomer) as string)) : null;
  const customer = customerLookup?.ok ? customerLookup.data : null;

  // -- which appliance: only ever among that customer's own -------------------------------------------
  const assetsResult = customer ? await attempt(api.customerAssets(customer.customer_id)) : null;
  const assets = assetsResult?.ok ? assetsResult.data : [];
  const assetParam = ENTITY_ID.test(sp.asset ?? "") ? (sp.asset as string) : null;
  const autoAsset = sp.change !== "asset" && customer?.customer_id === cr.entity_id && ar.state === "existing" ? ar.entity_id : null;
  const asset = assets.find((a) => a.asset_id === (assetParam ?? autoAsset)) ?? null;

  // -- what each step needs to show ---------------------------------------------------------------------
  const q = (sp.q ?? "").trim().slice(0, 100);
  const isPhoneQuery = /^[+\d][\d ()+-]{3,}$/.test(q);
  const [candidateLookups, searchResult, history, technicians] = await Promise.all([
    customer ? Promise.resolve([]) : Promise.all(cr.candidates.map((c) => attempt(api.customer(c.entity_id)))),
    !customer && q ? attempt(api.customers(isPhoneQuery ? { phone: q } : { q })) : Promise.resolve(null),
    asset ? attempt(api.assetHistory(asset.asset_id)) : Promise.resolve(null),
    asset ? technicianMap() : Promise.resolve(new Map()),
  ]);

  const customerCandidates: CandidateView[] = cr.candidates.flatMap((candidate, i) => {
    const lookup = candidateLookups[i];
    if (!lookup?.ok) return [];
    return [
      {
        id: candidate.entity_id,
        title: lookup.data.name,
        detail: customerDetail(lookup.data),
        score: candidate.match_score,
        reasons: candidate.reasons,
        href: null,
      },
    ];
  });
  const searchCandidates: CandidateView[] = (searchResult?.ok ? searchResult.data : []).map((c) => ({
    id: c.customer_id,
    title: c.name,
    detail: customerDetail(c),
    score: 0,
    reasons: [],
    href: null,
  }));

  const rankByMatch = new Map(ar.candidates.map((c) => [c.entity_id, c]));
  const usesResolvedCustomer = customer?.customer_id === cr.entity_id;
  const assetCandidates: CandidateView[] = assets
    .map((a) => {
      const match = usesResolvedCustomer ? rankByMatch.get(a.asset_id) : undefined;
      return { id: a.asset_id, title: applianceLabel(a), detail: assetDetail(a), score: match?.match_score ?? 0, reasons: match?.reasons ?? [], href: null };
    })
    .sort((a, b) => b.score - a.score);

  const memory = asset
    ? toMemory(asset.asset_id, applianceLabel(asset), history?.ok ? history.data.service_events : [], technicianNames(technicians), tz, now)
    : null;
  const form = jobFormDefaults(extraction, request.raw_text);
  const understood = understoodAs(extraction, tz, now);
  const matchedByKaamSetu = (kind: "customer" | "asset") =>
    kind === "customer" ? !chosenParam && customer?.customer_id === cr.entity_id && cr.state === "existing" : !assetParam && asset?.asset_id === ar.entity_id && ar.state === "existing";

  const stepOne = customer ? "done" : "current";
  const stepTwo = !customer ? "locked" : asset ? "done" : "current";
  const stepThree = customer && asset ? "current" : "locked";
  const changeLink = (label: string, href: string) => (
    <Link href={href} className="text-sm font-medium text-brand-strong hover:underline">
      {label}
    </Link>
  );

  return (
    <>
      <Link href="/" className="mb-4 inline-flex items-center gap-1.5 text-sm text-ink-2 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden />
        Job board
      </Link>
      <PageHeader
        title="Review request"
        subtitle="KaamSetu did not create a job for this on its own. Confirm who and what it is, then create the job."
        actions={<Badge>{request.status === "EXTRACTION_FAILED" ? "AI could not read it" : "Waiting for a person"}</Badge>}
      />

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="order-2 min-w-0 space-y-4 xl:order-1">
          {/* 1 · customer */}
          <ReviewStep
            index={1}
            title="Who is this?"
            state={stepOne}
            action={customer ? changeLink("Change", reviewUrl(id, { phone, change: "customer" })) : undefined}
          >
            {customer ? (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <Link href={`/customers/${customer.customer_id}`} className="font-semibold hover:underline">
                    {customer.name}
                  </Link>
                  <p className="text-sm text-ink-2">{customerDetail(customer)}</p>
                </div>
                {matchedByKaamSetu("customer") ? (
                  <Badge tone="ok">Matched by KaamSetu · {cr.candidates[0]?.reasons.join(", ") || "recorded evidence"}</Badge>
                ) : (
                  <Badge tone="brand">Confirmed by you</Badge>
                )}
              </div>
            ) : (
              <div className="space-y-5">
                {customerCandidates.length > 0 ? (
                  <div>
                    <p className="mb-2 text-sm text-ink-2">
                      {cr.state === "ambiguous"
                        ? "More than one customer could match. KaamSetu will not guess: choose the right one."
                        : "These customers came up. Choose one, or look someone up below."}
                    </p>
                    <CandidateList items={customerCandidates} hrefFor={(cid) => reviewUrl(id, { customer: cid, phone })} verb="This is them" />
                  </div>
                ) : null}

                <div>
                  <form action={`/requests/${id}`} role="search" className="flex gap-2">
                    {phone ? <input type="hidden" name="phone" value={phone} /> : null}
                    <div className="relative flex-1">
                      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
                      <input
                        name="q"
                        defaultValue={q}
                        aria-label="Look up an existing customer by name or phone"
                        placeholder="Look up by name or phone"
                        className={`${inputClass} pl-9`}
                      />
                    </div>
                    <Button type="submit" variant="secondary">
                      Look up
                    </Button>
                  </form>
                  {q ? (
                    <div className="mt-3">
                      {searchCandidates.length > 0 ? (
                        <CandidateList items={searchCandidates} hrefFor={(cid) => reviewUrl(id, { customer: cid, phone })} verb="This is them" />
                      ) : (
                        <p className="text-sm text-ink-2">No customer matches “{q}”.</p>
                      )}
                    </div>
                  ) : null}
                </div>

                <details open={cr.state === "new" || cr.state === "unresolved"} className="rounded-lg border border-line">
                  <summary className="flex min-h-11 cursor-pointer items-center px-3.5 py-2.5 text-sm font-medium select-none hover:bg-sunken">
                    {cr.state === "new" ? "Nobody on file matches: add them as a new customer" : "Not in the list? Add a new customer"}
                  </summary>
                  <div className="border-t border-line p-3.5">
                    <NewCustomerForm requestId={id} defaultName={customerFormDefaults(extraction).name} defaultPhone={phone} />
                  </div>
                </details>
              </div>
            )}
          </ReviewStep>

          {/* 2 · appliance */}
          <ReviewStep
            index={2}
            title="Which appliance?"
            state={stepTwo}
            action={asset && customer ? changeLink("Change", reviewUrl(id, { customer: customer.customer_id, phone, change: "asset" })) : undefined}
          >
            {asset ? (
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-semibold">{applianceLabel(asset)}</p>
                  <p className="text-sm text-ink-2">{assetDetail(asset) ?? "No further details recorded"}</p>
                </div>
                {matchedByKaamSetu("asset") ? <Badge tone="ok">Matched by KaamSetu · {ar.candidates[0]?.reasons.join(", ") || "recorded evidence"}</Badge> : <Badge tone="brand">Confirmed by you</Badge>}
              </div>
            ) : customer ? (
              <div className="space-y-4">
                {assetCandidates.length > 0 ? (
                  <div>
                    <p className="mb-2 text-sm text-ink-2">
                      {ar.state === "ambiguous" && usesResolvedCustomer
                        ? "The message fits more than one of this customer's appliances. The closest are first: choose the right one."
                        : `${customer.name}'s appliances. Choose the one this request is about.`}
                    </p>
                    <CandidateList items={assetCandidates} hrefFor={(aid) => reviewUrl(id, { customer: customer.customer_id, asset: aid, phone })} verb="This one" />
                  </div>
                ) : (
                  <p className="text-sm text-ink-2">{customer.name} has no appliances on file yet.</p>
                )}
                <details open={assetCandidates.length === 0 || ar.state === "new"} className="rounded-lg border border-line">
                  <summary className="flex min-h-11 cursor-pointer items-center px-3.5 py-2.5 text-sm font-medium select-none hover:bg-sunken">
                    {ar.state === "new" ? "This looks like a new appliance: add it" : "Not listed? Add a new appliance"}
                  </summary>
                  <div className="border-t border-line p-3.5">
                    <NewAssetForm requestId={id} customerId={customer.customer_id} phone={phone} defaults={assetFormDefaults(extraction)} />
                  </div>
                </details>
              </div>
            ) : null}
          </ReviewStep>

          {/* 3 · the job */}
          <ReviewStep index={3} title="Create the job" state={stepThree}>
            {customer && asset && memory ? (
              <div className="space-y-4">
                <ServiceMemoryRail memory={memory} current={{ label: "This request", text: request.raw_text }} recalledLabel="Recalled for this request" />
                <ConfirmJobForm
                  requestId={id}
                  customerId={customer.customer_id}
                  assetId={asset.asset_id}
                  defaultDescription={form.description}
                  defaultVisit={form.visitInput}
                  proposal={understood}
                />
              </div>
            ) : null}
          </ReviewStep>
          {stepThree === "locked" ? (
            <p className="px-1 text-sm text-ink-3">Nothing is created until you confirm a customer and an appliance.</p>
          ) : null}
        </div>

        <div className="order-1 min-w-0 xl:sticky xl:top-20 xl:order-2">
          <RequestContext
            rawText={request.raw_text}
            phone={formatPhone(phone) ?? phone}
            receivedLabel={formatDateTime(request.created_at, tz)}
            understood={understood}
            extraction={extraction}
            timeLabel={extraction ? describeTimePreference(extraction.data.timePreference, tz, now) : null}
            origin={provenance("manual", extraction)}
            safety={safety}
            failureReason={request.failure_reason}
          />
        </div>
      </div>
    </>
  );
}
