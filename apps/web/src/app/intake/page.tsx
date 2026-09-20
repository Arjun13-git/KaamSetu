import type { Metadata } from "next";

import { IntakeWorkspace } from "@/components/intake/IntakeWorkspace";
import { PageHeader } from "@/components/ui/Card";

export const metadata: Metadata = { title: "New request" };

export default async function IntakePage({ searchParams }: { searchParams: Promise<{ phone?: string }> }) {
  const { phone } = await searchParams;
  const initialPhone = /^[+\d ]{4,20}$/.test(phone ?? "") ? (phone as string) : "";
  return (
    <>
      <PageHeader
        title="New request"
        subtitle="A customer's message becomes a structured request, and then a job."
      />
      <IntakeWorkspace initialPhone={initialPhone} />
    </>
  );
}
