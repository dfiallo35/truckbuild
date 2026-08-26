const TIMELINES = ["Just exploring", "3–6 months", "1–3 months", "As soon as possible"];

const inputClasses =
  "border-border-strong bg-canvas-raised text-ink focus-visible:outline-accent w-full border px-4 py-3 text-sm focus-visible:outline-2 focus-visible:outline-offset-2";
const labelClasses = "font-data text-ink-faint text-xs tracking-[0.14em] uppercase";

export function ContactForm({ platformOptions }: { platformOptions: ReadonlyArray<string> }) {
  return (
    <form className="flex flex-col gap-6">
      <div className="grid gap-6 sm:grid-cols-2">
        <label className="flex flex-col gap-2">
          <span className={labelClasses}>Name</span>
          <input type="text" name="name" autoComplete="name" required className={inputClasses} />
        </label>
        <label className="flex flex-col gap-2">
          <span className={labelClasses}>Email</span>
          <input type="email" name="email" autoComplete="email" required className={inputClasses} />
        </label>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <label className="flex flex-col gap-2">
          <span className={labelClasses}>Phone (optional)</span>
          <input type="tel" name="phone" autoComplete="tel" className={inputClasses} />
        </label>
        <label className="flex flex-col gap-2">
          <span className={labelClasses}>Platform of interest</span>
          <select name="platform" defaultValue="" className={inputClasses}>
            <option value="">Not sure yet</option>
            {platformOptions.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>

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

      <label className="flex flex-col gap-2">
        <span className={labelClasses}>What are you building for?</span>
        <textarea
          name="intended_use"
          rows={4}
          placeholder="Payload, terrain, crew size — whatever tells us the job."
          className={`${inputClasses} resize-none`}
        />
      </label>

      <button
        type="submit"
        className="bg-accent text-accent-ink hover:bg-accent-hover font-display self-start px-8 py-3 text-sm font-medium tracking-[0.08em] uppercase transition-colors"
      >
        Send inquiry
      </button>
    </form>
  );
}
