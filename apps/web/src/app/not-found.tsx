import { SearchX } from "lucide-react";

import { LinkButton } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-1 py-16 text-center">
      <SearchX className="mb-2 size-6 text-ink-3" aria-hidden />
      <h1 className="text-lg font-semibold tracking-tight">We can&rsquo;t find that page</h1>
      <p className="text-ink-2">The record may have been removed, or the link is wrong.</p>
      <div className="mt-5">
        <LinkButton href="/" variant="primary">
          Back to the board
        </LinkButton>
      </div>
    </div>
  );
}
