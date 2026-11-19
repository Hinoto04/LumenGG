import { Platform, Share } from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import { exportMimeType, type ExportFormat } from "./collection-export";

/**
 * 내보내기 파일을 기기에 저장한다. 이미 의존성에 있는 expo-file-system과 React Native Share만 쓴다.
 * - Android: 저장소 접근 프레임워크(SAF)로 사용자가 고른 폴더에 파일을 만든다.
 * - iOS: 캐시 폴더에 파일을 쓰고 공유 시트로 넘겨 '파일에 저장' 등을 고르게 한다.
 * 사용자가 취소하면 false를 돌려준다.
 */
export async function saveExportFile(
  fileName: string,
  format: ExportFormat,
  content: string,
): Promise<boolean> {
  if (Platform.OS === "android") {
    const saf = FileSystem.StorageAccessFramework;
    const permission = await saf.requestDirectoryPermissionsAsync();
    if (!permission.granted) return false;
    // SAF는 MIME 형식에 맞는 확장자를 붙이므로 확장자를 뺀 이름을 넘긴다.
    const uri = await saf.createFileAsync(
      permission.directoryUri,
      fileName.replace(/\.[^.]+$/, ""),
      exportMimeType(format),
    );
    await FileSystem.writeAsStringAsync(uri, content, {
      encoding: FileSystem.EncodingType.UTF8,
    });
    return true;
  }
  const uri = FileSystem.cacheDirectory + fileName;
  await FileSystem.writeAsStringAsync(uri, content, {
    encoding: FileSystem.EncodingType.UTF8,
  });
  const result = await Share.share({ url: uri, title: fileName });
  return result.action !== Share.dismissedAction;
}

/** 파일 없이 내용을 텍스트로 공유한다(메신저 붙여넣기용). CSV의 BOM은 뺀다. */
export async function shareExportText(
  fileName: string,
  content: string,
): Promise<void> {
  await Share.share({ message: content.replace(/^\uFEFF/, ""), title: fileName });
}
