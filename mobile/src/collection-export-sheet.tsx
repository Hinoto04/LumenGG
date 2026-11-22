import React, { useMemo, useState } from "react";
import { Alert, Text, View } from "react-native";
import { useApp } from "./provider";
import { Button, Chip, Segmented, space, styles } from "./ui";
import { BottomSheet } from "./character-picker";
import {
  collectionExportFileName,
  defaultExportOptions,
  collectionExportEntries,
  formatCollectionExport,
  koreanExportHeaders,
  type ExportFormat,
  type ExportHeaders,
  type ExportOptions,
} from "./collection-export";
import { saveExportFile, shareExportText } from "./collection-export-file";
import type { CollectionItem } from "./types";

/** 컬렉션 화면에 보이는 목록(검색·필터·정렬 그대로)을 txt/csv로 저장하거나 공유하는 시트. */
export function CollectionExportSheet({
  visible,
  rows,
  onClose,
}: {
  visible: boolean;
  /** 컬렉션 화면이 지금 보여주는 행. */
  rows: CollectionItem[];
  onClose: () => void;
}) {
  const { catalog, language, amounts, t } = useApp();
  const [options, setOptions] = useState<ExportOptions>({
    ...defaultExportOptions,
  });
  const [busy, setBusy] = useState(false);
  const entries = useMemo(
    () =>
      catalog && visible
        ? collectionExportEntries(rows, catalog, amounts, language)
        : [],
    [catalog, visible, rows, amounts, language],
  );
  const headers = Object.fromEntries(
    Object.entries(koreanExportHeaders).map(([key, label]) => [key, t(label)]),
  ) as unknown as ExportHeaders;
  const toggle = (key: "code" | "rare" | "amount") =>
    setOptions((current) => ({ ...current, [key]: !current[key] }));
  async function run(kind: "file" | "text") {
    const fileName = collectionExportFileName(options.format);
    const content = formatCollectionExport(entries, options, headers);
    setBusy(true);
    try {
      if (kind === "text") await shareExportText(fileName, content);
      else if (await saveExportFile(fileName, options.format, content))
        onClose();
    } catch (error) {
      Alert.alert(
        t("내보내기에 실패했습니다."),
        error instanceof Error ? error.message : String(error),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <BottomSheet visible={visible} title="목록 내보내기" onClose={onClose}>
      {() => (
        <View style={{ gap: space.md, paddingBottom: space.md }}>
          <Text style={styles.muted}>
            {t("지금 보이는 목록을 검색·필터·정렬 그대로 내보냅니다.") +
              " " +
              entries.length.toLocaleString() +
              t("개")}
          </Text>
          <Segmented
            value={options.format}
            onChange={(format) =>
              setOptions((current) => ({
                ...current,
                format: format as ExportFormat,
              }))
            }
            values={[
              { key: "txt", label: "TXT" },
              { key: "csv", label: "CSV" },
            ]}
          />
          <View style={{ gap: space.xs }}>
            <Text style={styles.muted}>{t("포함할 열")}</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              <Chip label="카드명" selected icon="lock-closed" />
              <Chip
                label="코드"
                selected={options.code}
                onPress={() => toggle("code")}
              />
              <Chip
                label="레어도"
                selected={options.rare}
                onPress={() => toggle("rare")}
              />
              <Chip
                label="갯수"
                selected={options.amount}
                onPress={() => toggle("amount")}
              />
            </View>
          </View>
          <View style={{ flexDirection: "row", gap: space.sm }}>
            <Button
              label="텍스트로 공유"
              icon="share-outline"
              onPress={() => void run("text")}
              disabled={busy || !entries.length}
              style={{ flex: 1 }}
            />
            <Button
              label="파일로 저장"
              icon="download-outline"
              variant="primary"
              loading={busy}
              onPress={() => void run("file")}
              disabled={busy || !entries.length}
              style={{ flex: 1 }}
            />
          </View>
        </View>
      )}
    </BottomSheet>
  );
}
