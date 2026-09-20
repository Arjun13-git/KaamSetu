import type { Metadata } from "next";

import { IntakeWorkspace } from "@/components/intake/IntakeWorkspace";
import { PageHeader } from "@/components/ui/Card";

export const metadata: Metadata = { title: "New request" };

export default function IntakePage() {
  return (
    <>
      <PageHeader
        title="New request"
        subtitle="A customer's message becomes a structured request, and then a job."
      />
      <IntakeWorkspace />
    </>
  );
}
