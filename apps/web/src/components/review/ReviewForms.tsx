"use client";

import Link from "next/link";
import { BriefcaseBusiness, LoaderCircle, UserPlus } from "lucide-react";
import { useActionState } from "react";

import {
  confirmJobAction,
  createAssetAction,
  createCustomerAction,
  type ReviewFormState,
} from "@/app/requests/[id]/actions";
import { Button } from "@/components/ui/Button";
import { Field, FormProblem, fieldErrors, inputClass } from "@/components/ui/Field";
import { friendlyMessage } from "@/lib/api/errors";
import { ASSET_TYPE_OPTIONS, SERVICE_TYPE_OPTIONS, URGENCY_OPTIONS, reviewUrl } from "@/lib/review";
import { sentenceCase } from "@/lib/format";

const idle: ReviewFormState = { status: "idle" };

/** The value to show in a field: what was last typed if the form was refused, else its default. */
function valueOf(state: ReviewFormState, name: string, fallback: string): string {
  return state.status === "idle" ? fallback : (state.values[name] ?? fallback);
}

function problemOf(state: ReviewFormState): { errors: Record<string, string>; general: string | null } {
  if (state.status !== "error") return { errors: {}, general: null };
  const errors = fieldErrors(state.failure);
  // A field-level message is shown beside its field; anything else is shown once, above the button.
  return { errors, general: state.failure.fields.length === 0 ? friendlyMessage(state.failure) : null };
}

function Submit({ pending, icon, children }: { pending: boolean; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Button type="submit" variant="primary" disabled={pending}>
      {pending ? <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden /> : icon}
      {children}
    </Button>
  );
}

export function NewCustomerForm({
  requestId,
  defaultName,
  defaultPhone,
}: {
  requestId: string;
  defaultName: string;
  defaultPhone: string;
}) {
  const [state, action, pending] = useActionState(createCustomerAction, idle);
  const { errors, general } = problemOf(state);
  return (
    <form action={action} className="space-y-3" aria-busy={pending}>
      <input type="hidden" name="requestId" value={requestId} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Name" htmlFor="c-name" required error={errors.name}>
          <input id="c-name" name="name" defaultValue={valueOf(state, "name", defaultName)} autoComplete="off" className={inputClass} />
        </Field>
        <Field
          label="Phone"
          htmlFor="c-phone"
          error={errors.phone}
          hint={defaultPhone ? "Carried over from the message." : "The intake number is not stored with the request. Enter it if you have it."}
        >
          <input id="c-phone" name="phone" defaultValue={valueOf(state, "phone", defaultPhone)} inputMode="tel" autoComplete="off" className={inputClass} />
        </Field>
      </div>
      <Field label="Address" htmlFor="c-address" hint="Optional.">
        <input id="c-address" name="address" defaultValue={valueOf(state, "address", "")} autoComplete="off" className={inputClass} />
      </Field>

      {state.status === "duplicate" ? (
        <div role="alert" className="rounded-lg border border-ink-3 bg-surface px-3 py-2.5 text-sm">
          <p className="font-medium">That phone number already belongs to a customer.</p>
          <p className="mt-0.5 text-ink-2">Adding another would make every future message from this number ambiguous. Use the existing customer instead:</p>
          <ul className="mt-2 space-y-1">
            {state.customers.map((customer) => (
              <li key={customer.id}>
                <Link
                  href={reviewUrl(requestId, { customer: customer.id, phone: customer.phone ?? defaultPhone })}
                  className="font-medium text-brand-strong underline underline-offset-2"
                >
                  Use {customer.name}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <FormProblem message={general} />
      <Submit pending={pending} icon={<UserPlus className="size-4" aria-hidden />}>
        Add customer
      </Submit>
    </form>
  );
}

export function NewAssetForm({
  requestId,
  customerId,
  phone,
  defaults,
}: {
  requestId: string;
  customerId: string;
  phone: string;
  defaults: { assetType: string; brand: string; model: string };
}) {
  const [state, action, pending] = useActionState(createAssetAction, idle);
  const { errors, general } = problemOf(state);
  return (
    <form action={action} className="space-y-3" aria-busy={pending}>
      <input type="hidden" name="requestId" value={requestId} />
      <input type="hidden" name="customerId" value={customerId} />
      <input type="hidden" name="phone" value={phone} />
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Kind of appliance" htmlFor="a-type" required error={errors.assetType}>
          <select id="a-type" name="assetType" defaultValue={valueOf(state, "assetType", defaults.assetType)} className={inputClass}>
            <option value="" disabled>
              Choose…
            </option>
            {ASSET_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Brand" htmlFor="a-brand" hint="Leave empty if not stated.">
          <input id="a-brand" name="brand" defaultValue={valueOf(state, "brand", defaults.brand)} autoComplete="off" className={inputClass} />
        </Field>
        <Field label="Model" htmlFor="a-model" hint="Leave empty if not known.">
          <input id="a-model" name="model" defaultValue={valueOf(state, "model", defaults.model)} autoComplete="off" className={inputClass} />
        </Field>
        <Field label="Where is it?" htmlFor="a-location" hint="Optional, e.g. Bedroom.">
          <input id="a-location" name="location" defaultValue={valueOf(state, "location", "")} autoComplete="off" className={inputClass} />
        </Field>
      </div>
      <FormProblem message={general} />
      <Submit pending={pending} icon={<UserPlus className="size-4" aria-hidden />}>
        Add appliance
      </Submit>
    </form>
  );
}

export function ConfirmJobForm({
  requestId,
  customerId,
  assetId,
  defaultDescription,
  defaultVisit,
  proposal,
}: {
  requestId: string;
  customerId: string;
  assetId: string;
  defaultDescription: string;
  defaultVisit: string;
  /** What the API will use for anything left as proposed, in words. */
  proposal: string | null;
}) {
  const [state, action, pending] = useActionState(confirmJobAction, idle);
  const { errors, general } = problemOf(state);
  return (
    <form action={action} className="space-y-3" aria-busy={pending}>
      <input type="hidden" name="requestId" value={requestId} />
      <input type="hidden" name="customerId" value={customerId} />
      <input type="hidden" name="assetId" value={assetId} />
      <input type="hidden" name="descriptionDefault" value={defaultDescription} />
      <input type="hidden" name="visitDefault" value={defaultVisit} />
      {proposal ? <p className="rounded-lg bg-ai-tint/60 px-3 py-2 text-sm text-ink-2">Proposed from the AI reading: {proposal}</p> : null}
      <Field label="What needs doing" htmlFor="j-desc" required error={errors.description} hint="Starts from what the customer reported. Edit it if it is not right.">
        <textarea id="j-desc" name="description" rows={3} defaultValue={valueOf(state, "description", defaultDescription)} className={inputClass} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Type of work" htmlFor="j-type" error={errors.serviceType}>
          <select id="j-type" name="serviceType" defaultValue={valueOf(state, "serviceType", "")} className={inputClass}>
            <option value="">As proposed</option>
            {SERVICE_TYPE_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {sentenceCase(value)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Urgency" htmlFor="j-urgency" error={errors.urgency}>
          <select id="j-urgency" name="urgency" defaultValue={valueOf(state, "urgency", "")} className={inputClass}>
            <option value="">As proposed</option>
            {URGENCY_OPTIONS.map((value) => (
              <option key={value} value={value}>
                {value === "safety_critical" ? "Safety-critical" : sentenceCase(value)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Customer wants a visit" htmlFor="j-visit" error={errors.visit} hint="Leave as is to use what they asked for.">
          <input id="j-visit" name="visit" type="datetime-local" defaultValue={valueOf(state, "visit", defaultVisit)} className={inputClass} />
        </Field>
      </div>
      <FormProblem message={general} />
      <Submit pending={pending} icon={<BriefcaseBusiness className="size-4" aria-hidden />}>
        Confirm and create job
      </Submit>
    </form>
  );
}
