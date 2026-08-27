/**
 * Where `global-error.tsx` sends a client-side crash.
 *
 * The point of the round trip is that the browser has no error tracker in it -- deliberately,
 * since a marketing site should not ship one to every visitor to catch the rare failure. The
 * report lands on stderr in the same shape `instrumentation.ts` uses for server errors, so
 * both halves of a page's failure read as one stream in the platform's log view.
 *
 * Unauthenticated by necessity: it is called by a page that has just crashed, which has no
 * credential to offer. That makes it spammable, so it accepts a small body, keeps only fields
 * it recognises, and never echoes anything back that a caller could use to probe with.
 */

const MAX_BODY_BYTES = 8_000;

/** Cap a string so an oversized field cannot turn a log line into a log flood. */
function clip(value: unknown, max: number): string | null {
  return typeof value === "string" && value.length > 0 ? value.slice(0, max) : null;
}

export async function POST(request: Request): Promise<Response> {
  const raw = await request.text().catch(() => "");
  if (raw.length === 0 || raw.length > MAX_BODY_BYTES) {
    return new Response(null, { status: 204 });
  }

  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return new Response(null, { status: 204 });
  }

  if (typeof body !== "object" || body === null) {
    return new Response(null, { status: 204 });
  }

  const report = body as Record<string, unknown>;

  console.error(
    JSON.stringify({
      event: "client.error",
      source: "web",
      // The server's own id for the error, which is what makes this line joinable to the
      // `request.failed` line the same crash produced on the server.
      digest: clip(report.digest, 64),
      message: clip(report.message, 500),
      stack: clip(report.stack, 4_000),
      path: clip(report.path, 500),
      user_agent: clip(report.userAgent, 300),
    }),
  );

  // 204 always. A crashed page has nothing useful to do with a status, and a distinguishable
  // rejection would only tell someone probing this endpoint which bodies it likes.
  return new Response(null, { status: 204 });
}
