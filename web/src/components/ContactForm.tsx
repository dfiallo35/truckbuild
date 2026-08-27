"use client";

import { useActionState } from "react";

import {
  Field,
  FormNotice,
  SelectField,
  SpamControls,
  SubmitButton,
  TextAreaField,
  TimelineField,
} from "@/components/leads/LeadFields";
import { sendEnquiry } from "@/lib/actions";
import { IDLE_LEAD_STATE } from "@/lib/leads";

/**
 * The general enquiry. Same Server Action route, same storage and same spam controls as a
 * build request -- there is simply no build to price, so sales reads one list of leads rather
 * than two.
 */
export function ContactForm({
  platformOptions,
}: {
  platformOptions: ReadonlyArray<{ slug: string; name: string }>;
}) {
  const [state, action] = useActionState(sendEnquiry, IDLE_LEAD_STATE);

  return (
    <form action={action} className="flex flex-col gap-6">
      <FormNotice message={state.message} />
      <SpamControls />

      <div className="grid gap-6 sm:grid-cols-2">
        <Field label="Name" name="name" errors={state.errors} required autoComplete="name" />
        <Field
          label="Email"
          name="email"
          type="email"
          errors={state.errors}
          required
          autoComplete="email"
        />
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <Field
          label="Phone (optional)"
          name="phone"
          type="tel"
          errors={state.errors}
          autoComplete="tel"
        />
        <SelectField
          label="Platform of interest"
          name="platform_slug"
          errors={state.errors}
          emptyLabel="Not sure yet"
          options={platformOptions.map((platform) => ({
            value: platform.slug,
            label: platform.name,
          }))}
        />
      </div>

      <TimelineField />

      <TextAreaField
        label="What are you building for?"
        name="intended_use"
        errors={state.errors}
        placeholder="Payload, terrain, crew size — whatever tells us the job."
      />

      <SubmitButton>Send inquiry</SubmitButton>
    </form>
  );
}
