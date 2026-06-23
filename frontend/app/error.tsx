"use client";
import { useEffect } from "react";

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function Error({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  const isFirebase = error.message?.includes("Firebase") || error.message?.includes("firebase");
  const isNetwork = error.message?.includes("fetch") || error.message?.includes("network") || error.message?.includes("NetworkError");
  const isAuth = error.message?.includes("auth") || error.message?.includes("Auth") || error.message?.includes("unauthorized");

  function label(): string {
    if (isFirebase) return "Firebase connection failed";
    if (isNetwork) return "Network request failed";
    if (isAuth) return "Authentication error";
    return "An unexpected error occurred";
  }

  function detail(): string {
    if (isFirebase) return "Could not connect to Firebase. Check your network connection and try again.";
    if (isNetwork) return "Could not reach the server. Check your network connection and try again.";
    if (isAuth) return "Your session may have expired. Reload the page to sign in again.";
    return error.message || "No additional detail available.";
  }

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background p-8">
      <div className="w-full max-w-sm space-y-4">
        <div>
          <p className="text-subhead text-foreground">{label()}</p>
          <p className="text-caption text-muted-foreground mt-1">{detail()}</p>
          {error.digest && (
            <p className="text-caption text-muted-foreground mt-1 font-mono">
              Error ID: {error.digest}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={reset}
            className="px-4 py-2 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Retry
          </button>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-sm rounded-lg border border-border text-foreground hover:bg-secondary transition-colors"
          >
            Reload
          </button>
        </div>
      </div>
    </div>
  );
}
