import React, { useEffect, useRef, useState } from "react";
import {
  FlatList,
  View,
  Text,
  Pressable,
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  Keyboard,
} from "react-native";
import { router, Stack } from "expo-router";
import { useApp } from "../src/provider";
import { localized, normalizeSearch } from "../src/core";
import {
  Badge,
  Button,
  CachedImage,
  Chip,
  EmptyState,
  FilterButton,
  Notice,
  SearchInput,
  colors,
  radius,
  space,
  styles,
  tapFeedback,
} from "../src/ui";
import { preference, setPreference } from "../src/storage";
import {
  sortCards,
  isCardSort,
  type CardDisplay,
  type CardSort,
} from "../src/card-search";
import { CardSearchToolbar, CardSortMenu } from "../src/card-search-controls";
import { CardFilterScreen } from "../src/card-filter-screen";
import { CardStats } from "../src/card-stats";
import { CardImageViewer } from "../src/card-image-viewer";
import {
  activeCardFilters,
  activeFilterCount,
  emptyCardFilters,
  matchesCardFilters,
  rangeLabel,
  withoutCardFilter,
  type ActiveCardFilter,
  type CardFilters,
} from "../src/card-filters";
import type { Card } from "../src/types";

export default function Cards() {
  const { catalog, language, error, t, refresh } = useApp();
  const { width } = useWindowDimensions();
  const [display, setDisplay] = useState<CardDisplay>("grid"),
    [sort, setSort] = useState<CardSort>("code_asc"),
    [sortVisible, setSortVisible] = useState(false);
  const displayTouched = useRef(false),
    sortTouched = useRef(false),
    displayRef = useRef<CardDisplay>("grid");
  const [sortAnchor, setSortAnchor] = useState<number>();
  useEffect(() => {
    let active = true;
    Promise.all([
      preference<unknown>("card-search-display", "grid"),
      preference<unknown>("card-search-sort", "code_asc"),
    ])
      .then(([savedDisplay, savedSort]) => {
        if (!active) return;
        if (
          !displayTouched.current &&
          (savedDisplay === "grid" || savedDisplay === "detail")
        ) {
          displayRef.current = savedDisplay;
          setDisplay(savedDisplay);
        }
        if (!sortTouched.current && isCardSort(savedSort)) setSort(savedSort);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  function toggleDisplay() {
    displayTouched.current = true;
    const next = displayRef.current === "grid" ? "detail" : "grid";
    displayRef.current = next;
    setDisplay(next);
    setPreference("card-search-display", next).catch(() => undefined);
  }
  function selectSort(next: CardSort) {
    sortTouched.current = true;
    setSort(next);
    setSortVisible(false);
    setPreference("card-search-sort", next).catch(() => undefined);
  }
  const [query, setQuery] = useState("");
  const [filterVisible, setFilterVisible] = useState(false);
  const [filters, setFilters] = useState<CardFilters>({ ...emptyCardFilters });
  const [preview, setPreview] = useState<Card | null>(null);
  const needle = normalizeSearch(query);
  const filteredCards = (catalog?.cards || []).filter(
    (c) =>
      (!needle || c.search?.includes(needle)) && matchesCardFilters(c, filters),
  );
  const cards = sortCards(
    filteredCards,
    sort,
    language,
    catalog || { packs: [], collection: [] },
  );
  const columns = display === "grid" ? (width >= 700 ? 3 : 2) : 1;
  const tileWidth = (width - 32 - 12 * (columns - 1)) / columns;
  const imageHeight = tileWidth * 1.4;
  const filterCount = activeFilterCount(filters);
  const resetFilters = () => setFilters({ ...emptyCardFilters });
  const chipLabel = (filter: ActiveCardFilter) => {
    if (filter.kind === "range")
      return (
        t(filter.key === "frame" ? "속도" : "대미지") +
        " " +
        rangeLabel(filter.min, filter.max, t)
      );
    if (filter.key === "character") {
      const id = filter.value;
      const character = catalog?.characters.find((c) => String(c.id) === id);
      return character ? localized(character, language) : id;
    }
    return t(filter.value);
  };
  const openCard = (card: Card) =>
    router.push({ pathname: "/card/[id]", params: { id: card.id } });
  const showPreview = (card: Card) => {
    tapFeedback();
    setPreview(card);
  };
  const cardLabel = (card: Card) =>
    localized(card, language) + ", " + (card.code || "");
  return (
    <View style={[styles.screen, { paddingBottom: 0 }]}>
      <Stack.Screen options={{ headerRight: () => null }} />
      <CardSortMenu
        visible={sortVisible}
        value={sort}
        onSelect={selectSort}
        onClose={() => setSortVisible(false)}
        anchorY={sortAnchor}
      />
      <CardFilterScreen
        visible={filterVisible}
        value={filters}
        query={query}
        onClose={() => setFilterVisible(false)}
        onApply={(next) => {
          setFilters(next);
          setFilterVisible(false);
        }}
      />
      <CardImageViewer
        url={preview ? preview.img || preview.img_mid || preview.img_sm : ""}
        title={preview ? localized(preview, language) : ""}
        onClose={() => setPreview(null)}
      />
      <SearchInput
        value={query}
        onChangeText={setQuery}
        placeholder="카드 이름·효과 검색"
      />
      <View style={cardStyles.toolbar}>
        <FilterButton
          count={filterCount}
          onPress={() => {
            Keyboard.dismiss();
            setFilterVisible(true);
          }}
        />
        <Text style={[styles.muted, { flex: 1 }]}>
          {cards.length.toLocaleString()} {t("장")}
        </Text>
        <CardSearchToolbar
          display={display}
          onToggle={toggleDisplay}
          onSort={(bottom) => {
            setSortAnchor(bottom);
            setSortVisible(true);
          }}
          expanded={sortVisible}
        />
      </View>
      {filterCount > 0 && (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          style={{ flexGrow: 0, marginTop: space.sm }}
          contentContainerStyle={{ gap: space.sm }}
        >
          {activeCardFilters(filters).map((filter) => (
            <Chip
              key={filter.key}
              label={chipLabel(filter)}
              selected
              onRemove={() =>
                setFilters((current) => withoutCardFilter(current, filter.key))
              }
            />
          ))}
          <Chip label="초기화" icon="refresh" onPress={resetFilters} />
        </ScrollView>
      )}
      <Notice text={error} />
      {!catalog && <Button label="재시도" icon="refresh" onPress={refresh} />}
      <FlatList
        key={display + "-" + columns}
        numColumns={columns}
        columnWrapperStyle={columns > 1 ? { gap: 12 } : undefined}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        data={cards}
        keyExtractor={(c) => String(c.id)}
        contentContainerStyle={{ paddingTop: 12, paddingBottom: 32 }}
        initialNumToRender={8}
        windowSize={7}
        ListEmptyComponent={
          catalog ? (
            <EmptyState
              icon="search-outline"
              title="검색 결과가 없습니다."
              description={
                filterCount ? "필터를 줄이거나 초기화해 보세요." : undefined
              }
              action={
                filterCount
                  ? {
                      label: "필터 초기화",
                      icon: "refresh",
                      onPress: resetFilters,
                    }
                  : undefined
              }
            />
          ) : null
        }
        renderItem={({ item: c }) =>
          display === "grid" ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={cardLabel(c)}
              accessibilityHint={t("길게 누르면 크게 봅니다.")}
              onPress={() => openCard(c)}
              onLongPress={() => showPreview(c)}
              delayLongPress={300}
              style={({ pressed }) => [
                { width: tileWidth, marginBottom: space.lg },
                pressed && { opacity: 0.85, transform: [{ scale: 0.98 }] },
              ]}
            >
              <View style={cardStyles.tileImage}>
                <CachedImage
                  url={c.img_sm || c.img_mid || c.img}
                  fill
                  height={imageHeight}
                />
              </View>
              <Text numberOfLines={1} style={cardStyles.tileName}>
                {localized(c, language)}
              </Text>
              <Text numberOfLines={1} style={styles.muted}>
                {(c.code || "—") + " · " + t(c.type)}
              </Text>
            </Pressable>
          ) : (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={cardLabel(c)}
              onPress={() => openCard(c)}
              onLongPress={() => showPreview(c)}
              delayLongPress={300}
              style={({ pressed }) => [
                styles.panel,
                cardStyles.detailRow,
                pressed && { backgroundColor: colors.surface2 },
              ]}
            >
              <CachedImage url={c.img_sm || c.img_mid || c.img} height={132} />
              <View style={{ flex: 1, gap: 6 }}>
                <View>
                  <Text numberOfLines={1} style={cardStyles.rowName}>
                    {localized(c, language)}
                  </Text>
                  <View style={cardStyles.meta}>
                    <Text style={styles.muted}>{c.code || "—"}</Text>
                    <Badge label={c.type} tone="accent" />
                    {[c.pos, c.body, c.special].filter(Boolean).map((tag) => (
                      <Badge key={tag} label={tag} />
                    ))}
                  </View>
                </View>
                <CardStats card={c} compact />
                <Text numberOfLines={3} style={cardStyles.effect}>
                  {localized(c, language, "text")}
                </Text>
              </View>
            </Pressable>
          )
        }
      />
    </View>
  );
}

const cardStyles = StyleSheet.create({
  toolbar: { flexDirection: "row", alignItems: "center", gap: space.md },
  tileImage: { borderRadius: radius.md, overflow: "hidden" },
  tileName: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "700",
    marginTop: space.sm,
  },
  detailRow: { flexDirection: "row", gap: space.md, alignItems: "flex-start" },
  rowName: { color: colors.text, fontSize: 16, fontWeight: "700" },
  meta: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: 6,
    marginTop: 4,
  },
  effect: { color: colors.muted, fontSize: 13, lineHeight: 18 },
});
