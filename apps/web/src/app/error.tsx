"use client";

import { ErrorPanel } from "@/components/ui/States";
import { Button } from "@/components/ui/Button";

// Errors thrown while rendering are stripped of their message in production; the digest is what
// a developer can look up in the server log. Expected API failures are handled inline by pages.
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-lg py-12">
      <ErrorPanel
        title="Something went wrong on this page"
        failure={{ code: error.digest ? `ref ${error.digest}` : "RENDER_ERROR", message: "", status: 500, requestId: null, fields: [] }}
      />
      <div className="mt-4 flex justify-center">
        <Button variant="primary" onClick={reset}>
          Try again
        </Button>
      </div>
    </div>
  );
}
