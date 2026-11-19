import React, { useMemo, useState } from "react";
import { Alert, Text, View } from "react-native";
import { useApp } from "./provider";
import { Button, Chip, Segmented, space, styles } from "./ui";
import { BottomSheet } from "./character-picker";
import { COLLECTION_CATEGORIES } from "./collection-data";
import {
  collectionExportFileName,
  defaultExportOptions,
  favoriteExportEntries,
  formatCollectionExport,
  koreanExportHeaders,
  type ExportFormat,
  type ExportHeaders,
  type ExportOptions,
} from "./collection-export";
import { saveExportFile, shareExportText } from "./collection-export-file";

/** 컬렉션 즐겨찾기(하트) 목록을 txt/csv로 저장하거나 공유하는 시트. */
export function CollectionExportSheet({
  visible,
  onClose,
}: {
  visible: boolean;
  onClose: () => void;
}) {
  const { catalog, language, amounts, categories, t } = useApp();
  const [options, setOptions] = useState<ExportOptions>({
    ...defaultExportOptions,
  });
  const [heart, setHeart] = useState("");
  const [busy, setBusy] = useState(false);
  const entries = useMemo(
    () =>
      catalog && visible
        ? favoriteExportEntries(catalog, categories, amounts, language, heart)
        : [],
    [catalog, visible, categories, amounts, language, heart],
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
    <BottomSheet visible={visible} title="즐겨찾기 내보내기" onClose={onClose}>
      {() => (
        <View style={{ gap: space.md, paddingBottom: space.md }}>
          <Text style={styles.muted}>
            {t("하트를 붙인 카드를 속도 순으로 내보냅니다.") +
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
          <View style={{ gap: space.xs }}>
            <Text style={styles.muted}>{t("하트")}</Text>
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
              <Chip
                label="전체"
                selected={heart === ""}
                onPress={() => setHeart("")}
              />
              {COLLECTION_CATEGORIES.map((n) => (
                <Chip
                  key={n}
                  label={String(n)}
                  icon="heart"
                  selected={heart === String(n)}
                  onPress={() => setHeart(String(n))}
                />
              ))}
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
