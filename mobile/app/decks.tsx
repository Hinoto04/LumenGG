import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  View,
  Text,
  FlatList,
  Pressable,
  Keyboard,
  RefreshControl,
  StyleSheet,
} from "react-native";
import { router } from "expo-router";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import { matchingDecks } from "../src/deck-display";
import { request } from "../src/api";
import { preference, setPreference } from "../src/storage";
import { userMessage } from "../src/errors";
import type { Deck } from "../src/types";
import {
  DeckFilterScreen,
  defaultDeckFilters,
  type DeckFilters,
} from "../src/deck-filter-screen";
import {
  Badge,
  CachedImage,
  EmptyState,
  Fab,
  FilterButton,
  Icon,
  IconButton,
  Notice,
  SearchInput,
  Segmented,
  Skeleton,
  colors,
  radius,
  space,
  styles,
} from "../src/ui";
import { cellStyle, listColumns, useScreen } from "../src/layout";

export default function Decks() {
  const { decks, catalog, language, user, scope, sync, status, t } = useApp();
  // 가로 화면이나 넓은 화면에서는 목록을 여러 칸으로 놓는다.
  const { width, height } = useScreen();
  const listCols = listColumns(width);
  const landscape = width > height;
  const [filters, setFilters] = useState<DeckFilters>({
    ...defaultDeckFilters,
  });
  const [filterVisible, setFilterVisible] = useState(false);
  const { mode, character, trait = "", regulation = "" } = filters;
  const [query, setQuery] = useState(""),
    [results, setResults] = useState<Deck[]>([]),
    [nextPage, setNextPage] = useState<number | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [retry, setRetry] = useState(0);
  const generation = useRef(0);
  useEffect(() => {
    const ticket = ++generation.current;
    setResults([]);
    setNextPage(null);
    setMessage("");
    setBusy(false);
    if (mode !== "public") return;
    const cacheKey = `public-decks:${scope}:${query.trim()}:${character}:${trait}:${regulation}`;
    setBusy(true);
    const timer = setTimeout(async () => {
      try {
        const cached = await preference<Deck[]>(cacheKey, []);
        if (ticket !== generation.current) return;
        setResults(cached);
        const page = await request(
          `/decks?scope=public&q=${encodeURIComponent(query.trim())}&character_id=${character}&trait_card_id=${trait}&regulation_version_id=${regulation}`,
          {},
          false,
        );
        if (ticket !== generation.current) return;
        setResults(page.decks);
        setNextPage(page.next_page);
        await setPreference(cacheKey, page.decks);
      } catch (err) {
        if (ticket === generation.current) setMessage(userMessage(err));
      } finally {
        if (ticket === generation.current) setBusy(false);
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      generation.current++;
    };
  }, [mode, query, character, trait, regulation, scope, retry]);
  const data =
    mode === "mine"
      ? matchingDecks(decks, query, character, trait, regulation).reverse()
      : results;
  async function more() {
    if (!nextPage || busy) return;
    const ticket = generation.current;
    setBusy(true);
    try {
      const page = await request(
        `/decks?scope=public&q=${encodeURIComponent(query.trim())}&character_id=${character}&trait_card_id=${trait}&regulation_version_id=${regulation}&page=${nextPage}`,
        {},
        false,
      );
      if (ticket !== generation.current) return;
      const merged = [
        ...new Map([...results, ...page.decks].map((d) => [d.id, d])).values(),
      ] as Deck[];
      setResults(merged);
      setNextPage(page.next_page);
      setMessage("");
      await setPreference(
        `public-decks:${scope}:${query.trim()}:${character}:${trait}:${regulation}`,
        merged,
      );
    } catch (err) {
      if (ticket === generation.current) setMessage(userMessage(err));
    } finally {
      if (ticket === generation.current) setBusy(false);
    }
  }
  const filterCount =
    Number(!!character) + Number(!!trait) + Number(!!regulation);
  const characterName = (id: number) => {
    const c = catalog?.characters.find((c) => c.id === id);
    return c ? localized(c, language) : "";
  };
  const visibilityTone = (v: Deck["visibility"]) =>
    v === "public" ? "success" : v === "unlisted" ? "accent" : "neutral";
  const refreshList = () => (mode === "mine" ? sync() : setRetry((v) => v + 1));
  return (
    <View style={[styles.screen, { paddingBottom: 0 }]}>
      <View style={landscape ? landscapeBar : undefined}>
        <View style={landscape ? { width: 280, marginBottom: -12 } : undefined}>
          <Segmented
            value={mode}
            onChange={(next) =>
              setFilters((current) => ({
                ...current,
                mode: next as DeckFilters["mode"],
              }))
            }
            values={[
              { key: "mine", label: "내 덱", icon: "person-outline" },
              { key: "public", label: "공개 덱", icon: "globe-outline" },
            ]}
          />
        </View>
        <SearchInput
          value={query}
          onChangeText={setQuery}
          placeholder="덱 이름 · 작성자 · 키워드 검색"
          accessibilityLabel={t("덱 검색")}
          containerStyle={landscape ? { flex: 1, marginBottom: 0 } : undefined}
        />
        <View style={deckListStyles.toolbar}>
          <FilterButton
            count={filterCount}
            onPress={() => {
              Keyboard.dismiss();
              setFilterVisible(true);
            }}
          />
          <Text style={[styles.muted, !landscape && { flex: 1 }]}>
            {busy ? t("불러오는 중") : data.length + " " + t("덱")}
            {character ? " · " + characterName(Number(character)) : ""}
          </Text>
          <IconButton
            icon="refresh"
            label="새로고침"
            filled
            disabled={busy}
            onPress={refreshList}
          />
        </View>
      </View>
      <DeckFilterScreen
        visible={filterVisible}
        value={filters}
        query={query}
        onClose={() => setFilterVisible(false)}
        onApply={(next) => {
          setFilters(next);
          setFilterVisible(false);
        }}
      />
      <Notice text={mode === "mine" && user ? status : message} />
      <FlatList
        key={"columns-" + listCols}
        numColumns={listCols}
        columnWrapperStyle={listCols > 1 ? { gap: 12 } : undefined}
        data={mode === "mine" && !user ? [] : data}
        keyExtractor={(d) => d.uuid}
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingTop: space.sm, paddingBottom: 110 }}
        refreshControl={
          <RefreshControl
            refreshing={false}
            onRefresh={refreshList}
            tintColor={colors.accent}
            colors={[colors.accent]}
            progressBackgroundColor={colors.panel}
          />
        }
        onEndReachedThreshold={0.4}
        onEndReached={() => {
          if (mode === "public" && nextPage && !busy) void more();
        }}
        ListEmptyComponent={
          mode === "mine" && !user ? (
            <EmptyState
              icon="person-circle-outline"
              title="내 덱을 확인하려면 로그인해주세요."
              action={{
                label: "로그인",
                icon: "log-in-outline",
                onPress: () => router.push("/settings"),
              }}
            />
          ) : busy ? (
            <View style={{ gap: space.md }}>
              {[0, 1, 2].map((n) => (
                <Skeleton key={n} height={96} rounded={16} />
              ))}
            </View>
          ) : (
            <EmptyState
              icon="layers-outline"
              title="표시할 덱이 없습니다."
              action={
                mode === "mine"
                  ? {
                      label: "덱 만들기",
                      icon: "add",
                      onPress: () => router.push("/deck-editor"),
                    }
                  : undefined
              }
            />
          )
        }
        ListFooterComponent={
          mode === "public" && nextPage ? (
            <View style={{ paddingVertical: space.lg }}>
              <ActivityIndicator color={colors.accent} />
            </View>
          ) : null
        }
        renderItem={({ item: d }) => {
          const c = catalog?.characters.find((c) => c.id === d.character_id);
          const total = d.cards.reduce((n, e) => n + e.count, 0);
          return (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={d.name}
              onPress={async () => {
                if (mode === "public")
                  await setPreference(`deck-view:${scope}:${d.id}`, d).catch(
                    () => undefined,
                  );
                router.push({
                  pathname: "/deck/[id]",
                  params: { id: String(d.id) },
                });
              }}
              style={({ pressed }) => [
                deckListStyles.item,
                cellStyle(width, listCols),
                pressed && { backgroundColor: colors.surface2 },
              ]}
            >
              <View style={deckListStyles.portrait}>
                {c ? (
                  <CachedImage url={c.img_sm || c.img} height={88} fill />
                ) : (
                  <Icon name="person-outline" size={28} color={colors.subtle} />
                )}
              </View>
              <View style={{ flex: 1, gap: 4 }}>
                <Text numberOfLines={1} style={deckListStyles.name}>
                  {d.name}
                </Text>
                <Text numberOfLines={1} style={styles.muted}>
                  {(c ? localized(c, language) : "") +
                    " · " +
                    (d.author?.username || user?.username || "")}
                </Text>
                <View style={deckListStyles.badges}>
                  <Badge label={total + " " + t("장")} />
                  <Badge
                    label={d.visibility}
                    tone={visibilityTone(d.visibility)}
                  />
                  {!!d.locked && <Badge label="대회 제출" tone="danger" />}
                </View>
              </View>
              <Icon name="chevron-forward" size={18} color={colors.subtle} />
            </Pressable>
          );
        }}
      />
      <Fab
        label="덱 만들기"
        icon="add"
        onPress={() => router.push("/deck-editor")}
      />
    </View>
  );
}

const deckListStyles = StyleSheet.create({
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    marginBottom: space.xs,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    padding: space.md,
    marginBottom: space.md,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  portrait: {
    width: 64,
    height: 88,
    borderRadius: radius.md,
    overflow: "hidden",
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  name: { color: colors.text, fontSize: 17, fontWeight: "700" },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 2 },
});

// 가로 화면에서 검색창과 도구 줄을 한 줄로 합칠 때 쓰는 배치.
const landscapeBar = {
  flexDirection: "row" as const,
  alignItems: "center" as const,
  gap: 12,
  marginBottom: 4,
};
