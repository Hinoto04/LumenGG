import React, { useState } from "react";
import {
  View,
  Text,
  FlatList,
  Keyboard,
  Pressable,
  StyleSheet,
} from "react-native";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import {
  Badge,
  CachedImage,
  EmptyState,
  FilterButton,
  Icon,
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
  COLLECTION_CATEGORIES,
  categoryColors,
  collectionRows,
  collectionFilterCount,
  emptyCollectionFilters,
  type CollectionFilters,
} from "../src/collection-data";
import { BottomSheet } from "../src/character-picker";
import type { CollectionItem } from "../src/types";
import { cellStyle, listColumns, useScreen } from "../src/layout";

export default function Collection() {
  const {
    catalog,
    language,
    amounts,
    setAmount,
    categories,
    setCategory,
    status,
    t,
    syncErrors,
  } = useApp();
  // 분류(하트)를 고르는 중인 컬렉션 항목.
  const [picking, setPicking] = useState<CollectionItem | null>(null);
  // 가로 화면이나 넓은 화면에서는 목록을 여러 칸으로 놓는다.
  const { width, height } = useScreen();
  const listCols = listColumns(width);
  const landscape = width > height;
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<CollectionFilters>({
    ...emptyCollectionFilters,
  });
  const [filterVisible, setFilterVisible] = useState(false);
  const rows = catalog
    ? collectionRows(catalog, filters, query, amounts, language, categories)
    : [];
  const owned = rows.filter((c) => (amounts[c.id] || 0) > 0).length;
  const ratio = rows.length ? owned / rows.length : 0;
  return (
    <View style={[styles.screen, { paddingBottom: 0 }]}>
      <View style={landscape ? landscapeBar : undefined}>
        <SearchInput
          value={query}
          onChangeText={setQuery}
          placeholder="카드 이름·번호 검색"
          containerStyle={landscape ? { flex: 1, marginBottom: 0 } : undefined}
        />
        <View
          style={[
            collectionStyles.toolbar,
            landscape && { width: 380, marginBottom: 0 },
          ]}
        >
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
        key={"columns-" + listCols}
        numColumns={listCols}
        columnWrapperStyle={listCols > 1 ? { gap: 12 } : undefined}
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
          const category = categories[c.id] || 0;
          return (
            <View style={[collectionStyles.item, cellStyle(width, listCols)]}>
              <View style={collectionStyles.thumbWrap}>
                <View
                  style={[collectionStyles.thumb, !amount && { opacity: 0.45 }]}
                >
                  <CachedImage url={c.img_sm || c.image} height={90} fill />
                </View>
                {/* 웹과 같이 카드 이미지 왼쪽 위에 분류 하트를 붙인다. */}
                {!!category && (
                  <View
                    style={collectionStyles.heartBadge}
                    pointerEvents="none"
                    accessibilityElementsHidden
                    importantForAccessibility="no-hide-descendants"
                  >
                    <Icon
                      name="heart"
                      size={15}
                      color={categoryColors[category]}
                    />
                  </View>
                )}
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
                  <Pressable
                    accessibilityRole="button"
                    accessibilityLabel={
                      t("분류 지정") +
                      ": " +
                      (category ? t("하트") + " " + category : t("분류 없음"))
                    }
                    hitSlop={8}
                    onPress={() => {
                      Keyboard.dismiss();
                      setPicking(c);
                    }}
                    style={({ pressed }) => [
                      collectionStyles.heartButton,
                      pressed && { backgroundColor: colors.surface2 },
                    ]}
                  >
                    <Icon
                      name={category ? "heart" : "heart-outline"}
                      size={18}
                      color={
                        category ? categoryColors[category] : colors.subtle
                      }
                    />
                  </Pressable>
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
      <BottomSheet
        visible={!!picking}
        title="분류 지정"
        onClose={() => setPicking(null)}
      >
        {() => {
          if (!picking) return null;
          const card = catalog?.cards.find((x) => x.id === picking.card_id);
          const current = categories[picking.id] || 0;
          const choose = (value: number) => {
            setPicking(null);
            void setCategory(picking.id, value);
          };
          return (
            <View style={{ paddingBottom: space.md, gap: space.sm }}>
              <Text style={styles.muted} numberOfLines={1}>
                {(card ? localized(card, language) : picking.name) +
                  " · " +
                  picking.code +
                  (picking.rare ? " · " + picking.rare : "")}
              </Text>
              <View style={collectionStyles.categoryRow}>
                {COLLECTION_CATEGORIES.map((n) => (
                  <Pressable
                    key={n}
                    accessibilityRole="radio"
                    accessibilityLabel={t("하트") + " " + n}
                    accessibilityState={{ checked: current === n }}
                    onPress={() => choose(n)}
                    style={[
                      collectionStyles.categoryOption,
                      current === n && collectionStyles.categorySelected,
                    ]}
                  >
                    <Icon name="heart" size={28} color={categoryColors[n]} />
                    <Text style={styles.muted}>{n}</Text>
                  </Pressable>
                ))}
              </View>
              <Pressable
                accessibilityRole="radio"
                accessibilityState={{ checked: current === 0 }}
                onPress={() => choose(0)}
                style={[
                  collectionStyles.clearOption,
                  current === 0 && collectionStyles.categorySelected,
                ]}
              >
                <Icon
                  name="heart-dislike-outline"
                  size={20}
                  color={colors.muted}
                />
                <Text style={styles.text}>{t("분류 없음")}</Text>
              </Pressable>
            </View>
          );
        }}
      </BottomSheet>
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
  thumbWrap: { width: 64 },
  thumb: { width: 64, borderRadius: 6, overflow: "hidden" },
  heartBadge: {
    position: "absolute",
    top: 3,
    left: 3,
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(0, 0, 0, 0.55)",
  },
  heartButton: {
    width: 30,
    height: 30,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  categoryRow: {
    flexDirection: "row",
    gap: space.sm,
  },
  categoryOption: {
    flex: 1,
    minHeight: 64,
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    backgroundColor: colors.surface2,
  },
  categorySelected: {
    borderColor: colors.accent,
    borderWidth: 1.5,
    backgroundColor: colors.accentSoft,
  },
  clearOption: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: space.sm,
    minHeight: 48,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    backgroundColor: colors.surface2,
  },
  name: { color: colors.text, fontSize: 15, fontWeight: "600" },
  meta: {
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
