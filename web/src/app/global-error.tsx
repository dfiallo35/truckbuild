"use client";

import { useEffect } from "react";

/**
 * The client half of error tracking, and the last thing between a crash and a blank page.
 *
 * `global-error` replaces the root layout when it renders, which is why it carries its own
 * `<html>` and `<body>` and cannot use the app's fonts or components -- none of them are
 * mounted at this point. Styling is inline for the same reason: if the failure were in the
 * stylesheet, a page depending on it to look right would render unreadable.
 *
 * Reporting goes to the server rather than a client SDK. `navigator.sendBeacon` because the
 * visitor is quite likely to close the tab on seeing this, and a beacon survives that where a
 * fetch does not.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    const report = JSON.stringify({
      // The digest is the server's own id for this error; without it a production stack trace
      // is minified to uselessness, and with it the server log line is one search away.
      digest: error.digest ?? null,
      message: error.message,
      stack: error.stack ?? null,
      path: window.location.pathname + window.location.search,
      userAgent: navigator.userAgent,
    });

    try {
      const blob = new Blob([report], { type: "application/json" });
      if (!navigator.sendBeacon("/api/client-error", blob)) {
        void fetch("/api/client-error", { method: "POST", body: report, keepalive: true });
      }
    } catch {
      // Reporting a crash must never cause one.
    }
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "2rem",
          background: "#0b0b0c",
          color: "#f2f0ec",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
        }}
      >
        <main style={{ maxWidth: "32rem", textAlign: "center" }}>
          <p
            style={{
              margin: 0,
              fontSize: "0.625rem",
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color: "#84837f",
            }}
          >
            Something broke
          </p>
          <h1
            style={{
              margin: "0.75rem 0 0",
              fontSize: "1.75rem",
              letterSpacing: "-0.01em",
              textTransform: "uppercase",
            }}
          >
            This page did not load
          </h1>
          <p style={{ margin: "1rem 0 0", lineHeight: 1.6, color: "#a3a2a0" }}>
            The fault is ours and it has been reported. Trying again often works — a build you were
            configuring is stored in the address bar, not on this page, so it survives.
          </p>

          {error.digest ? (
            <p style={{ margin: "1.5rem 0 0", fontSize: "0.75rem", color: "#84837f" }}>
              Reference <code>{error.digest}</code>
            </p>
          ) : null}

          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "2rem",
              padding: "0.75rem 1.5rem",
              border: "none",
              background: "#f5a524",
              color: "#1a1206",
              font: "inherit",
              fontSize: "0.875rem",
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
