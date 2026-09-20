"use client";

import { ImagePlus, LoaderCircle, Phone, RotateCcw, Sparkles, X } from "lucide-react";
import { useRef, useState, useTransition } from "react";

import { Button } from "@/components/ui/Button";
import { Card, SectionLabel } from "@/components/ui/Card";
import { ErrorPanel } from "@/components/ui/States";
import { DEMO_MESSAGES, type DemoMessage } from "@/lib/demo-messages";
import { cn } from "@/lib/cn";
import { submitIntake, type IntakeState } from "@/app/intake/actions";
import { PipelinePreview } from "./PipelinePreview";
import { ResultPipeline } from "./ResultPipeline";

const newKey = () => crypto.randomUUID();
const MAX_PHOTO_BYTES = 3_500_000;

export function IntakeWorkspace({ initialPhone = "" }: { initialPhone?: string }) {
  const [text, setText] = useState("");
  const [phone, setPhone] = useState(initialPhone);
  const [photo, setPhoto] = useState<File | null>(null);
  const [photoProblem, setPhotoProblem] = useState<string | null>(null);
  // One key per distinct message. Submitting the same message again (a retry after a network error,
  // a double click) reuses it, so the API replays the first answer instead of creating a second job.
  const [key, setKey] = useState(newKey);
  const [state, setState] = useState<IntakeState>({ status: "idle" });
  const [sent, setSent] = useState<{ text: string; phone: string } | null>(null);
  const [pending, startTransition] = useTransition();
  const fileInput = useRef<HTMLInputElement>(null);

  const changed = () => setKey(newKey());

  function fill(message: DemoMessage) {
    setText(message.text);
    setPhone(message.phone);
    setPhoto(null);
    setKey(newKey());
    setState({ status: "idle" });
  }

  function pickPhoto(file: File | null) {
    setPhotoProblem(null);
    if (file && file.size > MAX_PHOTO_BYTES) {
      setPhotoProblem("That photo is larger than 3.5 MB.");
      if (fileInput.current) fileInput.current.value = "";
      return;
    }
    setPhoto(file);
    changed();
  }

  function reset() {
    setText("");
    setPhone("");
    setPhoto(null);
    setPhotoProblem(null);
    setKey(newKey());
    setState({ status: "idle" });
    setSent(null);
    if (fileInput.current) fileInput.current.value = "";
  }

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !text.trim()) return;
    const data = new FormData();
    data.set("text", text);
    data.set("phone", phone);
    data.set("key", key);
    if (photo) data.set("photo", photo);
    setSent({ text: text.trim(), phone: phone.trim() });
    startTransition(async () => {
      setState(await submitIntake(state, data));
    });
  }

  const fieldErrors =
    state.status === "error" ? Object.fromEntries(state.failure.fields.map((f) => [f.path, f.message])) : {};

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <div className="space-y-4 lg:sticky lg:top-20">
        <Card className="p-4 sm:p-5">
          <form onSubmit={onSubmit} className="space-y-4" aria-busy={pending}>
            <div>
              <label htmlFor="phone" className="mb-1.5 block text-sm font-medium">
                Customer phone <span className="font-normal text-ink-3">(recommended)</span>
              </label>
              <div className="relative">
                <Phone className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
                <input
                  id="phone"
                  name="phone"
                  inputMode="tel"
                  autoComplete="off"
                  value={phone}
                  onChange={(e) => {
                    setPhone(e.target.value);
                    changed();
                  }}
                  placeholder="90000 20001"
                  className="h-10 w-full rounded-lg border border-line-strong bg-surface pr-3 pl-9 text-sm placeholder:text-ink-3 focus:border-brand"
                />
              </div>
              {fieldErrors.phone ? <p className="mt-1 text-sm text-safety-strong">{fieldErrors.phone}</p> : null}
            </div>

            <div>
              <label htmlFor="text" className="mb-1.5 block text-sm font-medium">
                What the customer wrote
              </label>
              <textarea
                id="text"
                name="text"
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  changed();
                }}
                rows={5}
                maxLength={4000}
                placeholder="Paste a WhatsApp message, in any language…"
                className="w-full resize-y rounded-lg border border-line-strong bg-surface px-3 py-2.5 text-[15px] leading-6 placeholder:text-ink-3 focus:border-brand"
              />
              {fieldErrors.text ? <p className="mt-1 text-sm text-safety-strong">{fieldErrors.text}</p> : null}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input
                ref={fileInput}
                id="photo"
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="sr-only"
                onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)}
              />
              <label
                htmlFor="photo"
                className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 text-sm font-medium text-ink hover:bg-sunken has-[:focus-visible]:outline-2"
              >
                <ImagePlus className="size-4" aria-hidden />
                {photo ? "Change photo" : "Add photo"}
              </label>
              {photo ? (
                <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-sunken px-2.5 py-1 text-xs text-ink-2">
                  <span className="truncate">{photo.name}</span>
                  <button
                    type="button"
                    aria-label="Remove photo"
                    className="rounded-full p-0.5 hover:bg-line"
                    onClick={() => pickPhoto(null)}
                  >
                    <X className="size-3" />
                  </button>
                </span>
              ) : (
                <span className="text-xs text-ink-3">Optional. Shown to the AI, not stored.</span>
              )}
              {photoProblem || fieldErrors.photo ? (
                <p className="w-full text-sm text-safety-strong">{photoProblem ?? fieldErrors.photo}</p>
              ) : null}
            </div>

            <div className="flex items-center gap-2 pt-1">
              <Button type="submit" variant="primary" disabled={pending || !text.trim()} className="flex-1 sm:flex-none">
                {pending ? <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
                {pending ? "Reading the message…" : "Turn into a job"}
              </Button>
              {state.status !== "idle" || text ? (
                <Button variant="ghost" onClick={reset} disabled={pending}>
                  <RotateCcw className="size-4" aria-hidden />
                  Clear
                </Button>
              ) : null}
            </div>
          </form>
        </Card>

        <div>
          <SectionLabel className="mb-2">Demo messages</SectionLabel>
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            {DEMO_MESSAGES.map((message) => (
              <li key={message.id} className={message.hero ? "sm:col-span-2 lg:col-span-1 xl:col-span-2" : undefined}>
                <button
                  type="button"
                  onClick={() => fill(message)}
                  disabled={pending}
                  className={cn(
                    "w-full rounded-lg border px-3 py-2 text-left transition-colors disabled:opacity-60",
                    message.hero
                      ? "border-brand/50 bg-brand-tint hover:bg-brand-tint/70"
                      : "border-line bg-surface hover:bg-sunken",
                  )}
                >
                  <span className="block text-sm font-medium">
                    {message.label}
                    {message.hero ? <span className="ml-2 text-xs font-normal text-brand-strong">Start here</span> : null}
                  </span>
                  <span className="block text-xs text-ink-3">{message.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="min-w-0">
        <p role="status" className="sr-only">
          {pending
            ? "Reading the message"
            : state.status === "done"
              ? state.view.job
                ? "Done. A job was created."
                : "Done. This request needs a person to review it."
              : state.status === "error"
                ? "The request could not be processed."
                : ""}
        </p>
        {pending ? (
          <Card className="p-5">
            <div className="flex items-center gap-3">
              <LoaderCircle className="size-5 text-ai motion-safe:animate-spin" aria-hidden />
              <div>
                <p className="font-medium">Reading the message…</p>
                <p className="text-sm text-ink-3">The AI reads it, then KaamSetu checks who and what it refers to. Usually a few seconds.</p>
              </div>
            </div>
            {sent ? (
              <div className="mt-4 rounded-lg bg-sunken/70 px-4 py-3">
                <p className="mb-1 text-[11px] font-semibold tracking-wider text-ink-3 uppercase">
                  Customer wrote{sent.phone ? ` · ${sent.phone}` : ""}
                </p>
                <p className="text-[15px]">“{sent.text}”</p>
              </div>
            ) : null}
          </Card>
        ) : state.status === "done" ? (
          <ResultPipeline key={state.view.serviceRequestId} view={state.view} />
        ) : state.status === "error" ? (
          <ErrorPanel failure={state.failure} title="The request could not be processed" level={2} />
        ) : (
          <PipelinePreview />
        )}
      </div>
    </div>
  );
}
