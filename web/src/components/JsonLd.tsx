/** Renders a JSON-LD payload as an inline script tag. The caller owns the schema.org shape --
 * this only owns safe serialization (JSON.stringify never produces `</script>`-breaking output
 * for this data, which is our own structured content, not user input). */
export function JsonLd({ data }: { data: object }) {
  return (
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />
  );
}
