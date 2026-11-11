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

export default function Qna() {
  const { catalog, t } = useApp();
  const [query, setQuery] = useState(""),
    [faq, setFaq] = useState(false);
  const needle = normalizeSearch(query);
  const rows = (catalog?.qna || []).filter(
    (q) => (!needle || q.search?.includes(needle)) && (!faq || q.faq),
  );
  return (
    <View style={[styles.screen, { paddingBottom: 0 }]}>
      <SearchInput
        value={query}
        onChangeText={setQuery}
        placeholder="질문·카드 이름 검색"
      />
      <View style={qnaStyles.toolbar}>
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
      <FlatList
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
