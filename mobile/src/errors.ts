import { ApiError } from "./api";
export function userMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "다시 로그인해주세요.";
    if (error.status === 403) return "권한이 없습니다.";
    if (error.status === 409)
      return "최신 상태를 불러왔습니다. 다시 시도해주세요.";
    if (error.status >= 500 || error.status === 404)
      return "서버에 연결하지 못했습니다. 저장된 데이터로 이용할 수 있습니다.";
    const detail = error.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.join("\n");
    return (
      Object.values(detail || {})
        .flat()
        .map(String)
        .join("\n") || "요청을 확인해주세요."
    );
  }
  const message = error instanceof Error ? error.message : "";
  if (/SQLITE_FULL|no space|disk is full|storage full/i.test(message))
    return "저장 공간을 확보한 뒤 다시 시도해주세요.";
  if (/catalog|checksum|schema|SQLite|download|integrity/i.test(message))
    return "DB 업데이트를 완료하지 못했습니다. 기존 데이터를 사용합니다.";
  if (/^[가-힣]/.test(message)) return message;
  return "연결을 확인한 뒤 다시 시도해주세요. 저장된 데이터는 유지됩니다.";
}
