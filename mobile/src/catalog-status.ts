/**
 * 서버가 배포 중인 카탈로그(카드 DB)가 없다고 알려 온 응답인지 판단한다.
 * (/api/mobile/v1/catalog/manifest → 503 {"code": "catalog_unavailable"})
 *
 * 서버에 연결은 되었고 새 DB만 없는 상태이므로, 앱은 연결 오류로 알리지 않고
 * 내장되었거나 이전에 받아 둔 DB를 그대로 쓴다.
 */
export function isCatalogUnavailable(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const { status, detail } = error as { status?: unknown; detail?: unknown };
  return (
    status === 503 &&
    !!detail &&
    typeof detail === "object" &&
    (detail as { code?: unknown }).code === "catalog_unavailable"
  );
}
