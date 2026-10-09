import * as SecureStore from "expo-secure-store";

export const BASE_URL = (
  process.env.EXPO_PUBLIC_API_URL || "https://lumen.hinoto.kr"
).replace(/\/$/, "");
export function absoluteUrl(path: string): string {
  return /^https?:\/\//.test(path) ? path : BASE_URL + path;
}
let refreshFlight: Promise<string> | null = null;
let tokenGeneration = 0;
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: any,
  ) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}
export async function saveTokens(tokens: { access: string; refresh: string }) {
  tokenGeneration++;
  await SecureStore.setItemAsync("lumendb.tokens", JSON.stringify(tokens));
}
export async function clearTokens() {
  tokenGeneration++;
  await SecureStore.deleteItemAsync("lumendb.tokens");
}
async function tokens(): Promise<{ access: string; refresh: string } | null> {
  const value = await SecureStore.getItemAsync("lumendb.tokens");
  return value ? JSON.parse(value) : null;
}
async function refreshAccess(): Promise<string> {
  if (refreshFlight) return refreshFlight;
  const generation = tokenGeneration;
  refreshFlight = (async () => {
    const stored = await tokens();
    if (!stored) throw new ApiError(401, "로그인이 필요합니다.");
    const result = await request(
      "/auth/refresh",
      { method: "POST", body: JSON.stringify({ refresh: stored.refresh }) },
      false,
    );
    if (generation !== tokenGeneration)
      throw new ApiError(401, "Account changed.");
    await SecureStore.setItemAsync("lumendb.tokens", JSON.stringify(result));
    return result.access;
  })().finally(() => {
    refreshFlight = null;
  });
  return refreshFlight;
}
export async function request(
  path: string,
  init: RequestInit = {},
  authenticated = true,
  retried = false,
  expectedUserId?: number,
): Promise<any> {
  const stored = authenticated ? await tokens() : null;
  if (expectedUserId !== undefined) {
    const payload = stored?.access.split(".")[1];
    if (
      !payload ||
      Number(
        JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))).user_id,
      ) !== expectedUserId
    )
      throw new ApiError(401, "Account changed.");
  }
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (stored) headers.set("Authorization", "Bearer " + stored.access);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  let response: Response;
  try {
    response = await fetch(BASE_URL + "/api/mobile/v1" + path, {
      ...init,
      headers,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
  if (response.status === 401 && authenticated && stored && !retried) {
    await refreshAccess();
    return request(path, init, authenticated, true, expectedUserId);
  }
  const data =
    response.status === 204 || response.status === 304
      ? null
      : await response.json();
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}
export async function logIn(
  username: string,
  password: string,
  signup = false,
  email = "",
) {
  const result = await request(
    signup ? "/auth/signup" : "/auth/login",
    { method: "POST", body: JSON.stringify({ username, password, email }) },
    false,
  );
  await saveTokens(result);
  return request("/sync");
}
export async function logOut() {
  const value = await tokens();
  await clearTokens();
  if (value)
    await request(
      "/auth/logout",
      {
        method: "POST",
        headers: { Authorization: "Bearer " + value.access },
        body: JSON.stringify({ refresh: value.refresh }),
      },
      false,
    ).catch(() => undefined);
}
