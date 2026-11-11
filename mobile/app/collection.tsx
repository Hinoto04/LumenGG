import React, { useState } from "react";
import { View, Text, FlatList, Keyboard, StyleSheet } from "react-native";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import {
  Badge,
  CachedImage,
  EmptyState,
  FilterButton,
  Notice,
  SearchInput,
  Stepper,
  colors,
  radius,
  space,
  styles,
} from "../src/ui";
import { CollectionFilterScreen } from "../src/collection-filter-screen";
import {
  collectionRows,
  collectionFilterCount,
  emptyCollectionFilters,
  type CollectionFilters,
} from "../src/collection-data";

export default function Collection() {
  const { catalog, language, amounts, setAmount, status, t, syncErrors } =
    useApp();
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<CollectionFilters>({
    ...emptyCollectionFilters,
  });
  const [filterVisible, setFilterVisible] = useState(false);
  const rows = catalog
    ? collectionRows(catalog, filters, query, amounts, language)
    : [];
  const owned = rows.filter((c) => (amounts[c.id] || 0) > 0).length;
  const ratio = rows.length ? owned / rows.length : 0;
  return (
    <View style={[styles.screen, { paddingBottom: 0 }]}>
      <SearchInput
        value={query}
        onChangeText={setQuery}
        placeholder="카드 이름·번호 검색"
      />
      <View style={collectionStyles.toolbar}>
        <FilterButton
          count={collectionFilterCount(filters)}
          onPress={() => {
            Keyboard.dismiss();
            setFilterVisible(true);
          }}
        />
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={styles.muted}>
            {t("보유") +
              " " +
              owned.toLocaleString() +
              " / " +
              rows.length.toLocaleString() +
              " " +
              t("종")}
            {rows.length ? "  ·  " + Math.round(ratio * 100) + "%" : ""}
          </Text>
          <View
            style={collectionStyles.track}
            accessibilityRole="progressbar"
            accessibilityValue={{ min: 0, max: rows.length, now: owned }}
          >
            <View
              style={[collectionStyles.fill, { width: `${ratio * 100}%` }]}
            />
          </View>
        </View>
      </View>
      <CollectionFilterScreen
        visible={filterVisible}
        value={filters}
        query={query}
        onClose={() => setFilterVisible(false)}
        onApply={(next) => {
          setFilters(next);
          setFilterVisible(false);
        }}
      />
      <Notice text={status} />
      <FlatList
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        data={rows}
        keyExtractor={(c) => String(c.id)}
        contentContainerStyle={{ paddingTop: space.sm, paddingBottom: 32 }}
        initialNumToRender={10}
        windowSize={7}
        ListEmptyComponent={
          catalog ? (
            <EmptyState icon="grid-outline" title="검색 결과가 없습니다." />
          ) : null
        }
        renderItem={({ item: c }) => {
          const card = catalog?.cards.find((card) => card.id === c.card_id);
          const amount = amounts[c.id] || 0;
          const name = card ? localized(card, language) : c.name;
          return (
            <View style={collectionStyles.item}>
              <View
                style={[collectionStyles.thumb, !amount && { opacity: 0.45 }]}
              >
                <CachedImage url={c.img_sm || c.image} height={90} fill />
              </View>
              <View style={{ flex: 1, gap: 6 }}>
                <Text
                  style={[
                    collectionStyles.name,
                    !amount && { color: colors.muted },
                  ]}
                  numberOfLines={2}
                >
                  {name}
                </Text>
                <View style={collectionStyles.meta}>
                  <Text style={styles.muted}>{c.code}</Text>
                  {!!c.rare && <Badge label={c.rare} tone="accent" />}
                </View>
                {!!syncErrors[c.id] && (
                  <Text style={[styles.muted, { color: colors.danger }]}>
                    {t(syncErrors[c.id]!)}
                  </Text>
                )}
              </View>
              <Stepper
                label={name}
                value={amount}
                onChange={(next) =>
                  setAmount(c.id, (current) => current + (next - amount))
                }
              />
            </View>
          );
        }}
      />
    </View>
  );
}

const collectionStyles = StyleSheet.create({
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    marginBottom: space.xs,
  },
  track: {
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surface2,
    overflow: "hidden",
  },
  fill: {
    height: "100%",
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    padding: space.md,
    marginBottom: space.sm,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  thumb: { width: 64, borderRadius: 6, overflow: "hidden" },
  name: { color: colors.text, fontSize: 15, fontWeight: "600" },
  meta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
  },
});
