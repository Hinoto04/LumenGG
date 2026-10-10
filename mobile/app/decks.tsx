import React, { useEffect, useRef, useState } from "react";
import { View, Text, FlatList, Pressable, ScrollView } from "react-native";
import { router } from "expo-router";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import { matchingDecks } from "../src/deck-display";
import { request } from "../src/api";
import { preference, setPreference } from "../src/storage";
import { userMessage } from "../src/errors";
import type { Deck } from "../src/types";
import {
  styles,
  colors,
  Button,
  Input,
  Choices,
  CachedImage,
  Notice,
} from "../src/ui";

export default function Decks() {
  const { decks, catalog, language, user, scope, sync, status, t } = useApp();
  const [mode, setMode] = useState("mine"),
    [query, setQuery] = useState(""),
    [character, setCharacter] = useState(""),
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
    const cacheKey = `public-decks:${scope}:${query.trim()}:${character}`;
    setBusy(true);
    const timer = setTimeout(async () => {
      try {
        const cached = await preference<Deck[]>(cacheKey, []);
        if (ticket !== generation.current) return;
        setResults(cached);
        const page = await request(
          `/decks?scope=public&q=${encodeURIComponent(query.trim())}&character_id=${character}`,
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
  }, [mode, query, character, scope, retry]);
  const data =
    mode === "mine"
      ? user
        ? matchingDecks(decks, query, character).reverse()
        : []
      : results;
  async function more() {
    if (!nextPage || busy) return;
    const ticket = generation.current;
    setBusy(true);
    try {
      const page = await request(
        `/decks?scope=public&q=${encodeURIComponent(query.trim())}&character_id=${character}&page=${nextPage}`,
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
        `public-decks:${scope}:${query.trim()}:${character}`,
        merged,
      );
    } catch (err) {
      if (ticket === generation.current) setMessage(userMessage(err));
    } finally {
      if (ticket === generation.current) setBusy(false);
    }
  }
  return (
    <View style={styles.screen}>
      <Choices
        value={mode}
        onChange={setMode}
        values={[
          { key: "mine", label: t("내 덱") },
          { key: "public", label: t("공개 덱 검색") },
        ]}
      />
      <Input
        value={query}
        onChangeText={setQuery}
        placeholder={t("덱 이름 · 작성자 · 키워드 검색")}
        accessibilityLabel={t("덱 검색")}
      />
      <ScrollView
        horizontal
        style={{ flexGrow: 0 }}
        showsHorizontalScrollIndicator={false}
      >
        <Choices
          value={character}
          onChange={setCharacter}
          values={[
            { key: "", label: t("전체 캐릭터") },
            ...(catalog?.characters || []).map((c) => ({
              key: String(c.id),
              label: localized(c, language),
            })),
          ]}
        />
      </ScrollView>
      {mode === "mine" && !user && (
        <View style={styles.panel}>
          <Notice text="내 덱을 확인하려면 로그인해주세요." />
          <Button label="로그인" onPress={() => router.push("/settings")} />
        </View>
      )}
      <View style={[styles.row, { marginBottom: 8 }]}>
        <Text style={styles.muted}>
          {busy ? t("불러오는 중") : `${data.length} ${t("덱")}`}
        </Text>
        <Button
          label="새로고침"
          disabled={busy}
          onPress={() => (mode === "mine" ? sync() : setRetry((v) => v + 1))}
        />
      </View>
      <Notice text={mode === "mine" && user ? status : message} />
      <FlatList
        data={data}
        keyExtractor={(d) => d.uuid}
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
        ListEmptyComponent={
          !busy && (mode !== "mine" || !!user) ? (
            <Notice text="표시할 덱이 없습니다." />
          ) : null
        }
        ListFooterComponent={
          mode === "public" && nextPage ? (
            <Button label="더 보기" onPress={more} disabled={busy} />
          ) : null
        }
        renderItem={({ item: d }) => {
          const c = catalog?.characters.find((c) => c.id === d.character_id);
          return (
            <Pressable
              style={styles.panel}
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
            >
              <View style={styles.row}>
                {c && (
                  <View style={{ width: 56 }}>
                    <CachedImage url={c.img_sm || c.img} height={70} fill />
                  </View>
                )}
                <View style={{ flex: 1 }}>
                  <Text
                    style={[styles.title, { fontSize: 18, marginBottom: 6 }]}
                  >
                    {d.name}
                  </Text>
                  <Text style={styles.muted}>
                    {d.author?.username || user?.username} ·{" "}
                    {c ? localized(c, language) : ""}
                  </Text>
                  <Text style={[styles.muted, { marginTop: 5 }]}>
                    {d.cards.reduce((n, e) => n + e.count, 0)} {t("장")} ·{" "}
                    {t(d.visibility)}
                  </Text>
                </View>
                <Text style={{ color: colors.accent, fontSize: 24 }}>›</Text>
              </View>
            </Pressable>
          );
        }}
      />
    </View>
  );
}
