import { EmptyState } from "@/components/ui/States";
import { LinkButton } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-16">
      <EmptyState title="We can't find that page" hint="The record may have been removed, or the link is wrong." />
      <div className="flex justify-center">
        <LinkButton href="/" variant="primary">
          Back to the board
        </LinkButton>
      </div>
    </div>
  );
}
