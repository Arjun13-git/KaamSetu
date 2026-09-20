"use client";

import { X } from "lucide-react";
import { useEffect, useRef } from "react";

/** A modal built on the native <dialog>: focus trapping, Escape and the backdrop come with it. */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      aria-labelledby="dialog-title"
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-(--radius-card) border border-line bg-surface p-0 text-ink shadow-pop backdrop:bg-ink/40"
    >
      {open ? (
        <div className="p-5">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h2 id="dialog-title" className="text-lg font-semibold tracking-tight">
                {title}
              </h2>
              {description ? <p className="mt-1 text-sm text-ink-2">{description}</p> : null}
            </div>
            <button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1 text-ink-3 hover:bg-sunken hover:text-ink">
              <X className="size-5" />
            </button>
          </div>
          {children}
        </div>
      ) : null}
    </dialog>
  );
}
