import Link from "next/link";
import { CalendarClock, Mail, MapPin, Phone, UserRound, Wrench } from "lucide-react";

import { UnknownValue } from "@/components/ui/Ai";
import { Badge } from "@/components/ui/Badge";
import { Card, SectionLabel } from "@/components/ui/Card";
import type { Asset, Customer, Technician } from "@/lib/api/types";
import { applianceLabel, formatDate, formatPhone } from "@/lib/format";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className="mt-0.5 text-sm break-words text-ink">{children}</dd>
    </div>
  );
}

export function CustomerPanel({ customer }: { customer: Customer }) {
  const phone = formatPhone(customer.phone);
  return (
    <Card className="p-4">
      <SectionLabel className="mb-3">Customer</SectionLabel>
      <Link href={`/customers/${customer.customer_id}`} className="text-base font-semibold hover:underline">
        {customer.name}
      </Link>
      <ul className="mt-2 space-y-1.5 text-sm text-ink-2">
        {phone ? (
          <li className="flex items-center gap-2">
            <Phone className="size-4 text-ink-3" aria-hidden />
            <a href={`tel:${customer.phone}`} className="hover:underline">
              {phone}
            </a>
          </li>
        ) : null}
        {customer.email ? (
          <li className="flex items-center gap-2">
            <Mail className="size-4 text-ink-3" aria-hidden />
            {customer.email}
          </li>
        ) : null}
        {customer.address ? (
          <li className="flex items-start gap-2">
            <MapPin className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
            {customer.address}
          </li>
        ) : null}
      </ul>
      {customer.notes ? <p className="mt-3 rounded-lg bg-sunken/70 px-3 py-2 text-sm text-ink-2">{customer.notes}</p> : null}
    </Card>
  );
}

export function AppliancePanel({ asset, tz }: { asset: Asset; tz: string }) {
  return (
    <Card className="p-4">
      <SectionLabel className="mb-3">Appliance</SectionLabel>
      <p className="text-base font-semibold">{applianceLabel(asset)}</p>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5">
        <Field label="Model">{asset.model ?? <UnknownValue label="Not recorded" />}</Field>
        <Field label="Serial number">{asset.serial_number ?? <UnknownValue label="Not recorded" />}</Field>
        <Field label="Location">{asset.location ?? <UnknownValue label="Not recorded" />}</Field>
        <Field label="Warranty until">{asset.warranty_until ? formatDate(`${asset.warranty_until}T12:00:00Z`, tz) : <UnknownValue label="Not recorded" />}</Field>
      </dl>
    </Card>
  );
}

export function TechnicianPanel({ technician }: { technician: Technician | null }) {
  return (
    <Card className="p-4">
      <SectionLabel className="mb-3">Technician</SectionLabel>
      {technician ? (
        <>
          <p className="flex items-center gap-2 text-base font-semibold">
            <UserRound className="size-4 text-ink-3" aria-hidden />
            {technician.name}
            {technician.active ? null : <Badge>Inactive</Badge>}
          </p>
          {technician.phone ? <p className="mt-1 text-sm text-ink-2">{formatPhone(technician.phone)}</p> : null}
          {technician.skills.length > 0 ? (
            <p className="mt-2 flex flex-wrap gap-1.5">
              {technician.skills.map((skill) => (
                <Badge key={skill}>
                  <Wrench className="size-3" aria-hidden />
                  {skill.replace(/_/g, " ")}
                </Badge>
              ))}
            </p>
          ) : null}
        </>
      ) : (
        <p className="text-sm text-ink-2">No technician assigned yet.</p>
      )}
    </Card>
  );
}

export function SchedulePanel({
  scheduled,
  preferred,
  created,
  completed,
}: {
  scheduled: string | null;
  preferred: string | null;
  created: string;
  completed: string | null;
}) {
  return (
    <Card className="p-4">
      <SectionLabel className="mb-3">Timing</SectionLabel>
      <dl className="space-y-2.5">
        <Field label="Scheduled visit">
          {scheduled ? (
            <span className="inline-flex items-center gap-1.5">
              <CalendarClock className="size-4 text-ink-3" aria-hidden />
              {scheduled}
            </span>
          ) : (
            <UnknownValue label="Not scheduled" />
          )}
        </Field>
        <Field label="Customer prefers">{preferred ?? <UnknownValue label="No preference given" />}</Field>
        <Field label="Created">{created}</Field>
        {completed ? <Field label="Completed">{completed}</Field> : null}
      </dl>
    </Card>
  );
}
