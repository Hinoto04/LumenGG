/**
 * Django JSON 요청. POST는 CSRF 토큰이 필요하다.
 * /battlelog/play/는 csrftoken 쿠키를 심어 주므로, 쿠키가 없으면(개발 서버 등) 한 번 들러서 받는다.
 */

function readCookie(name: string): string {
  const match = document.cookie.split("; ").find((item) => item.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : "";
}

async function csrfToken(): Promise<string> {
  let token = readCookie("csrftoken");
  if (!token) {
    await fetch("/battlelog/play/", { credentials: "same-origin" }).catch(() => undefined);
    token = readCookie("csrftoken");
  }
  return token;
}

export class RequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function parse<T>(response: Response): Promise<T> {
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    /* 본문 없는 오류 */
  }
  if (!response.ok || (data && typeof data === "object" && (data as { ok?: boolean }).ok === false)) {
    const message = (data as { error?: string } | null)?.error || `요청을 처리하지 못했습니다. (HTTP ${response.status})`;
    throw new RequestError(message, response.status);
  }
  return data as T;
}

export async function getJson<T>(url: string): Promise<T> {
  return parse<T>(await fetch(url, { credentials: "same-origin" }));
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  const token = await csrfToken();
  const response = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify(body),
  });
  return parse<T>(response);
}

export function uid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  // randomUUID가 없는 환경(비보안 출처의 LAN 주소 등)용. 서버는 UUID 형식만 확인한다.
  const hex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20)}`;
}
