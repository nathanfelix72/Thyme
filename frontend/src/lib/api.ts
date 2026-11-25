import { fetchAuthSession } from "aws-amplify/auth";
import { cognitoConfigured } from "./amplify";

/**
 * Empty = same origin.
 * Local Vite proxies /api → :8765. Production CloudFront routes /api/* → EC2.
 */
const apiBase = (import.meta.env.VITE_API_BASE as string | undefined)?.trim() || "";

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
      // Not signed in
    }
  }

  return fetch(`${apiBase}${path}`, { ...init, headers });
}
