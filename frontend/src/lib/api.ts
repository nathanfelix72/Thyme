import { fetchAuthSession } from "aws-amplify/auth";
import { cognitoConfigured } from "./amplify";

/** Empty = same origin (Vite proxy locally, or misconfigured prod). */
let apiBase = (import.meta.env.VITE_API_BASE as string | undefined)?.trim() || "";

/**
 * Load runtime API base from /api-config.json (uploaded when the laptop tunnel starts).
 * Call once before rendering the app so production CloudFront can reach a tunnel URL
 * without rebuilding the whole frontend.
 */
export async function initApiBase(): Promise<void> {
  try {
    const res = await fetch("/api-config.json", { cache: "no-store" });
    if (!res.ok) return;
    const data = (await res.json()) as { apiBase?: unknown };
    if (typeof data.apiBase === "string" && data.apiBase.trim()) {
      apiBase = data.apiBase.trim().replace(/\/$/, "");
    }
  } catch {
    /* keep VITE_API_BASE / empty */
  }
}

export function getApiBase(): string {
  return apiBase;
}

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers || {});
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!headers.has("Content-Type") && init.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }

  if (cognitoConfigured) {
    try {
      const session = await fetchAuthSession();
      const token =
        session.tokens?.accessToken?.toString() ||
        session.tokens?.idToken?.toString();
      if (token) headers.set("Authorization", `Bearer ${token}`);
    } catch {
      // Not signed in — local API still accepts local-dev
    }
  }

  return fetch(`${apiBase}${path}`, { ...init, headers });
}
