/**
 * Server-side error tracking for the web app.
 *
 * `onRequestError` is Next's own hook for an uncaught error during a server render, a Server
 * Action, or a route handler. Using it rather than a client SDK is deliberate: it costs the
 * browser nothing, and the errors it catches are the ones that actually take a page down.
 * Client-side errors are reported from `global-error.tsx` instead.
 *
 * The report is a structured line on stderr. Vercel ingests those and makes them searchable
 * per deployment, so this is a working error surface with no vendor and no key to rotate; the
 * API service is the one wired to Sentry, because that is where a failure is silent rather
 * than visible as a broken page. If this side ever needs the same, `@sentry/nextjs` slots in
 * here without the call sites changing.
 */

export function register() {
  // Nothing to initialise while reporting is stderr-only. This export must still exist:
  // Next only treats the file as an instrumentation module when it is present.
}

type ErrorContext = {
  routerKind: string;
  routePath: string;
  routeType: string;
};

type ErrorRequest = {
  path: string;
  method: string;
  headers: Record<string, string | undefined>;
};

export function onRequestError(error: unknown, request: ErrorRequest, context: ErrorContext) {
  // The same header the API stamps on its responses. When a page fails because its catalog
  // fetch failed, this is what ties the two services' records of it together.
  const requestId = request.headers["x-request-id"];

  console.error(
    JSON.stringify({
      event: "request.failed",
      source: "web",
      request_id: requestId ?? null,
      method: request.method,
      path: request.path,
      // The route template rather than the resolved URL, so failures group by page.
      route: context.routePath,
      route_type: context.routeType,
      router: context.routerKind,
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    }),
  );
}
