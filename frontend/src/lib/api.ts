import { toast } from "sonner";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage.getItem("access_token");
}

function setToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem("access_token", token);
}

function clearToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem("access_token");
}

type AuthMode = "required" | "none";

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  auth: AuthMode = "required",
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (auth === "required") {
    const token = getToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401 && auth === "required") {
    clearToken();
    toast.error("Session expired");

    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }

    throw new Error("Session expired");
  }

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));

    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export { apiFetch, getToken, setToken, clearToken, API_URL };
export type { AuthMode };
