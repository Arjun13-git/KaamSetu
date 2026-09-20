export function Logo({ className }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className ?? ""}`}>
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
        <rect width="32" height="32" rx="8" fill="var(--color-brand)" />
        {/* a bridge ("setu"): the span between a message and a job */}
        <path d="M5 21h22" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M7 21c0-6 4-9 9-9s9 3 9 9" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" fill="none" />
        <path d="M11 21v-4M16 21v-6M21 21v-4" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" opacity=".75" />
      </svg>
      <span className="hidden text-[17px] font-semibold tracking-tight text-ink sm:inline">KaamSetu</span>
    </span>
  );
}
