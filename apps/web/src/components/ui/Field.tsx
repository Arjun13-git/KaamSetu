import { cn } from "@/lib/cn";

export const inputClass =
  "w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm placeholder:text-ink-3 focus:border-brand focus:outline-none aria-[invalid=true]:border-safety";

export function Field({
  label,
  htmlFor,
  error,
  hint,
  required,
  className,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  hint?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium">
        {label}
        {required ? <span className="text-safety"> *</span> : null}
      </label>
      {children}
      {hint && !error ? <p className="mt-1 text-xs text-ink-3">{hint}</p> : null}
      {error ? (
        <p role="alert" className="mt-1 text-sm text-safety-strong">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function fieldErrors(failure: { fields: Array<{ path: string; message: string }> } | null | undefined): Record<string, string> {
  return Object.fromEntries((failure?.fields ?? []).map((f) => [f.path, f.message]));
}

export function FormProblem({ message, className }: { message: string | null; className?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className={cn("rounded-lg border border-safety-line bg-safety-tint px-3 py-2 text-sm text-safety-strong", className)}>
      {message}
    </p>
  );
}
