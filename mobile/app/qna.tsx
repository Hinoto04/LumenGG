import React, { useState } from "react";
import { View, Text, FlatList, Pressable, StyleSheet } from "react-native";
import { router } from "expo-router";
import { useApp } from "../src/provider";
import { normalizeSearch } from "../src/core";
import {
  Badge,
  Chip,
  EmptyState,
  Icon,
  SearchInput,
  colors,
  radius,
  space,
  styles,
} from "../src/ui";
import { cellStyle, listColumns, useScreen } from "../src/layout";

export default function Qna() {
  const { catalog, t } = useApp();
  // 가로 화면이나 넓은 화면에서는 목록을 여러 칸으로 놓는다.
  const { width, height } = useScreen();
  const listCols = listColumns(width);
  const landscape = width > height;
  const [query, setQuery] = useState(""),
    [faq, setFaq] = useState(false);
  const needle = normalizeSearch(query);
  const rows = (catalog?.qna || []).filter(
    (q) => (!needle || q.search?.includes(needle)) && (!faq || q.faq),
  );
  return (
    <View style={[styles.screen, { paddingBottom: 0 }]}>
      <View style={landscape ? landscapeBar : undefined}>
        <SearchInput
          value={query}
          onChangeText={setQuery}
          placeholder="질문·카드 이름 검색"
          containerStyle={landscape ? { flex: 1, marginBottom: 0 } : undefined}
        />
        <View style={[qnaStyles.toolbar, landscape && { marginBottom: 0 }]}>
          <Chip
            label="FAQ"
            icon={faq ? "star" : "star-outline"}
            selected={faq}
            onPress={() => setFaq(!faq)}
          />
          <Text style={styles.muted}>
            {rows.length.toLocaleString() + " " + t("개")}
          </Text>
        </View>
      </View>
      <FlatList
        key={"columns-" + listCols}
        numColumns={listCols}
        columnWrapperStyle={listCols > 1 ? { gap: 12 } : undefined}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        data={rows}
        keyExtractor={(q) => String(q.id)}
        contentContainerStyle={{ paddingBottom: 32 }}
        ListEmptyComponent={
          catalog ? (
            <EmptyState icon="search-outline" title="검색 결과가 없습니다." />
          ) : null
        }
        renderItem={({ item: q }) => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={q.title}
            style={({ pressed }) => [
              qnaStyles.item,
              cellStyle(width, listCols),
              pressed && { backgroundColor: colors.surface2 },
            ]}
            onPress={() =>
              router.push({ pathname: "/qna/[id]", params: { id: q.id } })
            }
          >
            <View style={qnaStyles.mark}>
              <Text style={qnaStyles.markText}>Q</Text>
            </View>
            <View style={{ flex: 1, gap: 6 }}>
              <Text style={qnaStyles.title} numberOfLines={3}>
                {q.title}
              </Text>
              <View style={qnaStyles.tags}>
                {q.faq && <Badge label="FAQ" tone="accent" />}
                {!!q.tags && (
                  <Text style={styles.muted} numberOfLines={1}>
                    {q.tags}
                  </Text>
                )}
              </View>
            </View>
            <Icon name="chevron-forward" size={18} color={colors.subtle} />
          </Pressable>
        )}
      />
    </View>
  );
}

const qnaStyles = StyleSheet.create({
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    marginBottom: space.md,
  },
  item: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: space.md,
    padding: 14,
    marginBottom: space.sm,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  mark: {
    width: 28,
    height: 28,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  markText: { color: colors.accent, fontWeight: "800", fontSize: 14 },
  title: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 21,
    fontWeight: "600",
  },
  tags: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
});

// 가로 화면에서 검색창과 도구 줄을 한 줄로 합칠 때 쓰는 배치.
const landscapeBar = {
  flexDirection: "row" as const,
  alignItems: "center" as const,
  gap: 12,
  marginBottom: 4,
};
