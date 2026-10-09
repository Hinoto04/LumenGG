import React, { useEffect, useRef, useState } from "react";
import {
  FlatList,
  View,
  Text,
  Pressable,
  useWindowDimensions,
  Keyboard,
} from "react-native";
import { router, Stack } from "expo-router";
import { useApp } from "../src/provider";
import { localized, normalizeSearch } from "../src/core";
import { styles, Input, CachedImage, Notice, Button } from "../src/ui";
import { preference, setPreference } from "../src/storage";
import {
  sortCards,
  isCardSort,
  type CardDisplay,
  type CardSort,
} from "../src/card-search";
import { CardSearchToolbar, CardSortMenu } from "../src/card-search-controls";
import { CardFilterScreen } from "../src/card-filter-screen";
import {
  activeFilterCount,
  emptyCardFilters,
  matchesCardFilters,
  type CardFilters,
} from "../src/card-filters";

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
  const imageHeight = Math.max(140, (tileWidth - 22) * 1.4);
  return (
    <View style={styles.screen}>
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
      <Input
        value={query}
        onChangeText={setQuery}
        placeholder={t("카드 검색")}
      />
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 8,
            flex: 1,
          }}
        >
          <Button
            label={`${t("필터")}${activeFilterCount(filters) ? ` (${activeFilterCount(filters)})` : ""}`}
            onPress={() => {
              Keyboard.dismiss();
              setFilterVisible(true);
            }}
          />
          <Text style={styles.muted}>
            {cards.length} {t("장")}
          </Text>
        </View>
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
      <Notice text={error} />
      {!catalog && <Button label="재시도" onPress={refresh} />}
      <FlatList
        key={`${display}-${columns}`}
        numColumns={columns}
        columnWrapperStyle={columns > 1 ? { gap: 12 } : undefined}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        data={cards}
        keyExtractor={(c) => String(c.id)}
        contentContainerStyle={{ paddingTop: 12 }}
        ListEmptyComponent={<Notice text={t("검색 결과가 없습니다.")} />}
        renderItem={({ item: c }) => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${localized(c, language)}, ${c.code || ""}`}
            style={[
              styles.panel,
              display === "grid" && { width: tileWidth, padding: 10 },
            ]}
            onPress={() =>
              router.push({ pathname: "/card/[id]", params: { id: c.id } })
            }
          >
            {display === "grid" ? (
              <>
                <CachedImage
                  url={c.img_sm || c.img_mid || c.img}
                  fill
                  height={imageHeight}
                />
                <Text
                  numberOfLines={2}
                  style={[
                    styles.text,
                    { fontWeight: "700", marginTop: 10, minHeight: 40 },
                  ]}
                >
                  {localized(c, language)}
                </Text>
                <Text numberOfLines={1} style={styles.muted}>
                  {c.code || "—"}
                </Text>
              </>
            ) : (
              <View style={styles.row}>
                <CachedImage url={c.img_sm || c.img_mid || c.img} />
                <View style={{ flex: 1 }}>
                  <Text style={[styles.text, { fontWeight: "700" }]}>
                    {localized(c, language)}
                  </Text>
                  <Text style={styles.muted}>
                    {c.code} · {t(c.type)}
                  </Text>
                  <Text style={styles.text}>
                    {t("속도")} {c.frame ?? "—"} · {t("대미지")}{" "}
                    {c.damage ?? "—"}
                  </Text>
                  <Text style={styles.muted}>
                    {[c.pos, c.body, c.special]
                      .filter(Boolean)
                      .map(t)
                      .join(" · ")}
                  </Text>
                  <Text style={styles.muted}>
                    Hit {c.hit || "—"} · Guard {c.guard || "—"} · Counter{" "}
                    {c.counter || "—"}
                  </Text>
                  {c.type.includes("수비") && (
                    <Text style={styles.muted}>
                      {t("상단")} {c.g_top || "—"} · {t("중단")}{" "}
                      {c.g_mid || "—"} · {t("하단")} {c.g_bot || "—"}
                    </Text>
                  )}
                  <Text
                    numberOfLines={4}
                    style={[styles.text, { marginTop: 6 }]}
                  >
                    {localized(c, language, "text")}
                  </Text>
                </View>
              </View>
            )}
          </Pressable>
        )}
      />
    </View>
  );
}
