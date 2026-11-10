import { postJson } from "./http";
import { currentTarget } from "./live";

/**
 * 자동 판정 문제 제보(battlelog:simulatorReportIssue). 관리자 검수 화면에서 확인한다.
 * - 사용자가 적은 제보: kind=user
 * - 브라우저 오류 자동 보고: kind=client_error (같은 오류는 한 번만)
 * 좌석으로 접속한 플레이어만 보낼 수 있다.
 */

let lastReportId = "";

function reportUrl(): { url: string; seat: string; seat_token: string } | null {
  const target = currentTarget();
  if (!target?.seat) return null;
  return {
    url: `/battlelog/simulator/${encodeURIComponent(target.view)}/report/`,
    seat: target.seat,
    seat_token: target.token,
  };
}

export async function reportIssue(details: string): Promise<string> {
  const route = reportUrl();
  if (!route) throw new Error("좌석으로 접속한 플레이어만 제보할 수 있습니다.");
  const { url, ...seat } = route;
  const data = await postJson<{ report_id: string }>(url, {
    ...seat,
    kind: "user",
    details: details.slice(0, 4000),
    report_id: lastReportId,
  });
  lastReportId = data.report_id || lastReportId;
  return lastReportId;
}

const reported = new Set<string>();

function reportClientError(value: unknown, context: string) {
  const route = reportUrl();
  if (!route || reported.size >= 20) return;
  const error = (value && typeof value === "object" ? value : {}) as Record<string, unknown>;
  const diagnostic = {
    error_type: String(error.name ?? "ClientError").slice(0, 120),
    message: String(error.message ?? value ?? "브라우저 오류").slice(0, 500),
    source: String(error.filename ?? "").slice(0, 1000),
    line: Number(error.lineno ?? 0),
    column: Number(error.colno ?? 0),
    stack: String(error.stack ?? "").slice(0, 4000),
    context,
  };
  const fingerprint = `${diagnostic.error_type}|${diagnostic.message}|${diagnostic.context}`;
  if (reported.has(fingerprint)) return;
  reported.add(fingerprint);
  const { url, ...seat } = route;
  postJson<{ report_id: string }>(url, { ...seat, kind: "client_error", diagnostic })
    .then((data) => {
      lastReportId = data.report_id || lastReportId;
    })
    .catch(() => undefined);
}

let installed = false;

/** 실제 대전 화면에서 한 번만 건다. */
export function installErrorReporter() {
  if (installed) return;
  installed = true;
  window.addEventListener("error", (event) => reportClientError(event.error ?? event, "uncaught_error"));
  window.addEventListener("unhandledrejection", (event) => reportClientError(event.reason, "unhandled_rejection"));
}
