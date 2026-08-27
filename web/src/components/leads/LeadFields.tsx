"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useFormStatus } from "react-dom";

import { HONEYPOT_FIELD, STARTED_AT_FIELD, type LeadFieldErrors } from "@/lib/leads";

/**
 * The shared parts of both lead forms.
 *
 * Errors are rendered where the mistake is, in the accent the rest of the site uses for
 * "needs attention", and wired to the input with `aria-describedby` so a screen reader hears
 * the reason rather than just "invalid".
 */

const inputClasses =
  "border-border-strong bg-canvas-raised text-ink focus-visible:outline-accent w-full border px-4 py-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 aria-[invalid=true]:border-accent";

const labelClasses = "font-data text-ink-faint text-xs tracking-[0.14em] uppercase";

function FieldErrors({ id, messages }: { id: string; messages: string[] }) {
  if (messages.length === 0) return null;
  return (
    <p id={id} className="text-accent text-xs">
      {messages.join(" ")}
    </p>
  );
}

type FieldProps = {
  label: string;
  name: string;
  errors: LeadFieldErrors;
  type?: string;
  required?: boolean;
  autoComplete?: string;
  defaultValue?: string;
};

export function Field({
  label,
  name,
  errors,
  type = "text",
  required = false,
  autoComplete,
  defaultValue,
}: FieldProps) {
  const messages = errors[name] ?? [];
  const errorId = `${name}-error`;

  return (
    <label className="flex flex-col gap-2">
      <span className={labelClasses}>{label}</span>
      <input
        type={type}
        name={name}
        required={required}
        autoComplete={autoComplete}
        defaultValue={defaultValue}
        aria-invalid={messages.length > 0}
        aria-describedby={messages.length > 0 ? errorId : undefined}
        className={inputClasses}
      />
      <FieldErrors id={errorId} messages={messages} />
    </label>
  );
}

export function TextAreaField({
  label,
  name,
  errors,
  placeholder,
  rows = 4,
}: {
  label: string;
  name: string;
  errors: LeadFieldErrors;
  placeholder?: string;
  rows?: number;
}) {
  const messages = errors[name] ?? [];
  const errorId = `${name}-error`;

  return (
    <label className="flex flex-col gap-2">
      <span className={labelClasses}>{label}</span>
      <textarea
        name={name}
        rows={rows}
        placeholder={placeholder}
        aria-invalid={messages.length > 0}
        aria-describedby={messages.length > 0 ? errorId : undefined}
        className={`${inputClasses} resize-none`}
      />
      <FieldErrors id={errorId} messages={messages} />
    </label>
  );
}

export function SelectField({
  label,
  name,
  errors,
  options,
  emptyLabel,
  defaultValue = "",
}: {
  label: string;
  name: string;
  errors: LeadFieldErrors;
  options: ReadonlyArray<{ value: string; label: string }>;
  emptyLabel?: string;
  defaultValue?: string;
}) {
  const messages = errors[name] ?? [];
  const errorId = `${name}-error`;

  return (
    <label className="flex flex-col gap-2">
      <span className={labelClasses}>{label}</span>
      <select
        name={name}
        defaultValue={defaultValue}
        aria-invalid={messages.length > 0}
        aria-describedby={messages.length > 0 ? errorId : undefined}
        className={inputClasses}
      >
        {emptyLabel ? <option value="">{emptyLabel}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <FieldErrors id={errorId} messages={messages} />
    </label>
  );
}

export const TIMELINES = [
  "Just exploring",
  "3–6 months",
  "1–3 months",
  "As soon as possible",
] as const;

export function TimelineField() {
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className={labelClasses}>Timeline</legend>
      <div className="flex flex-wrap gap-4">
        {TIMELINES.map((timeline) => (
          <label key={timeline} className="text-ink-muted flex items-center gap-2 text-sm">
            <input type="radio" name="timeline" value={timeline} className="accent-accent" />
            {timeline}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/**
 * The two spam controls the form is responsible for: a field only a script would fill, and
 * when the form was rendered.
 *
 * The timestamp is written after mount rather than during render, so a form served from a
 * prerendered page does not report the time the page was built. With JavaScript off it stays
 * empty, and the API treats an unreported timing as no evidence at all.
 */
export function SpamControls() {
  const startedAt = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (startedAt.current) startedAt.current.value = String(Date.now());
  }, []);

  return (
    <>
      <input ref={startedAt} type="hidden" name={STARTED_AT_FIELD} defaultValue="" />
      <div className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label htmlFor="lead-website" aria-hidden="true">
          Website
        </label>
        {/* `aria-hidden` sits on the input rather than a wrapper: hiding a container that
            still holds a focusable control is what trips assistive technology. With
            `tabIndex={-1}` it is unreachable by keyboard, so nobody meets it by accident. */}
        <input
          id="lead-website"
          type="text"
          name={HONEYPOT_FIELD}
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
        />
      </div>
    </>
  );
}

/** The headline for a rejection that is not about one field. */
export function FormNotice({ message }: { message: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="border-accent/40 bg-accent/5 text-ink border-l-2 px-4 py-3 text-sm">
      {message}
    </p>
  );
}

export function SubmitButton({ children, disabled }: { children: ReactNode; disabled?: boolean }) {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending || disabled}
      className="bg-accent text-accent-ink hover:bg-accent-hover focus-visible:outline-accent font-display self-start px-8 py-3 text-sm font-medium tracking-[0.08em] uppercase transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {pending ? "Sending…" : children}
    </button>
  );
}
