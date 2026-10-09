import React, { useState, useEffect, useRef } from "react";
import { View, Text, ScrollView, Alert } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import * as Crypto from "expo-crypto";
import type { Deck, Card } from "../../src/types";
import { useApp } from "../../src/provider";
import {
  localized,
  normalizeSearch,
  adjustEntry,
  deckError,
} from "../../src/core";
import {
  styles,
  Button,
  Input,
  Choices,
  CachedImage,
  Notice,
} from "../../src/ui";
export default function DeckEditor() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const app = useApp();
  const { catalog, language, t } = app;
  const initialScope = useRef(app.scope);
  const [deck, setDeckState] = useState<Deck>(
    () =>
      app.decks.find((d) => d.uuid === id) || {
        uuid: Crypto.randomUUID(),
        name: "",
        character_id: catalog?.characters[0]?.id || 1,
        description: "",
        keyword: "",
        tags: "",
        visibility: "private",
        cards: [],
      },
  );
  const edited = useRef(false);
  function setDeck(next: React.SetStateAction<Deck>) {
    edited.current = true;
    setDeckState(next);
  }
  const [query, setQuery] = useState(""),
    [message, setMessage] = useState(""),
    [selectedOnly, setSelectedOnly] = useState(false),
    [ready, setReady] = useState(false);
  useEffect(() => {
    setReady(true);
  }, []);
  useEffect(() => {
    if (initialScope.current !== app.scope) {
      router.back();
      return;
    }
    if (!ready || deck.locked || !edited.current) return;
    app
      .saveDeck(deck)
      .then((issue) => setMessage(issue || t("저장 완료")))
      .catch(() => setMessage(t("초안 저장을 확인해주세요.")));
  }, [deck, app.scope, ready]);
  if (!catalog)
    return (
      <View style={styles.screen}>
        <Notice text="DB를 불러오는 중입니다." />
      </View>
    );
  const needle = normalizeSearch(query);
  const candidateCards = catalog.cards.filter(
    (c) =>
      (selectedOnly
        ? deck.cards.some((e) => e.card_id === c.id)
        : c.character_id === deck.character_id ||
          c.character_id === 1 ||
          (deck.character_id === 15 && c.type === "공격")) &&
      (!needle || c.search?.includes(needle)),
  );
  const missing = deck.cards.filter(
    (e) => !catalog.cards.some((c) => c.id === e.card_id),
  );
  const count = deck.cards.reduce(
    (s, e) =>
      s +
      (!catalog.cards.find((c) => c.id === e.card_id)?.ultimate ? e.count : 0),
    0,
  );
  function change(card: Card, field: "count" | "hand" | "side", delta: number) {
    if (deck.locked) return;
    setDeck((d) =>
      adjustEntry(d, card, field, delta, catalog!.rules.copy_limits),
    );
  }
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      <Input
        value={deck.name}
        onChangeText={(name) => setDeck((d) => ({ ...d, name }))}
        placeholder={t("덱 이름")}
        editable={!deck.locked}
      />
      <Choices
        value={String(deck.character_id)}
        onChange={(value) => {
          if (!deck.locked)
            setDeck((d) => ({ ...d, character_id: Number(value) }));
        }}
        values={catalog.characters.map((c) => ({
          key: String(c.id),
          label: localized(c, language),
        }))}
      />
      <Choices
        value={deck.visibility}
        onChange={(value) => {
          if (!deck.locked)
            setDeck((d) => ({ ...d, visibility: value as Deck["visibility"] }));
        }}
        values={["private", "unlisted", "public"].map((v) => ({
          key: v,
          label: t(v),
        }))}
      />
      <Input
        value={deck.description}
        onChangeText={(description) => setDeck((d) => ({ ...d, description }))}
        placeholder={t("설명")}
        multiline
        editable={!deck.locked}
      />
      <Text style={styles.text}>
        {count} /{" "}
        {catalog.rules.max_deck_sizes[String(deck.character_id)] ?? 21} ·{" "}
        {t("손패")} {deck.cards.reduce((s, c) => s + c.hand, 0)}
      </Text>
      <Notice text={message} />
      <Button
        label="저장"
        disabled={deck.locked}
        onPress={async () => {
          const issue = await app.saveDeck(deck);
          Alert.alert(
            t(issue ? "초안 저장" : "저장 완료"),
            issue ? t(issue) : "",
          );
        }}
      />
      <Input
        value={query}
        onChangeText={setQuery}
        placeholder={t("카드 검색")}
      />
      <Button
        label={selectedOnly ? "전체" : "선택한 카드"}
        onPress={() => setSelectedOnly(!selectedOnly)}
      />
      {missing.map((e) => (
        <View style={styles.panel} key={e.card_id}>
          <Text style={styles.text}>
            {e.name || `#${e.card_id}`} · {t("사용할 수 없는 카드가 있습니다.")}
          </Text>
          <Button
            label="제거"
            onPress={() =>
              setDeck((d) => ({
                ...d,
                cards: d.cards.filter((c) => c.card_id !== e.card_id),
              }))
            }
          />
        </View>
      ))}
      {candidateCards.map((card) => {
        const entry = deck.cards.find((e) => e.card_id === card.id);
        return (
          <View style={styles.panel} key={card.id}>
            <View style={styles.row}>
              <CachedImage url={card.img_sm || card.img_mid} />
              <View style={{ flex: 1 }}>
                <Text style={styles.text}>{localized(card, language)}</Text>
                <Text style={styles.muted}>
                  {card.code} · {t(card.type)}
                </Text>
                <View style={styles.row}>
                  <Button
                    label="−"
                    disabled={deck.locked || !entry}
                    onPress={() => change(card, "count", -1)}
                  />
                  <Text style={styles.text}>{entry?.count || 0}</Text>
                  <Button
                    label="+"
                    disabled={deck.locked}
                    onPress={() => change(card, "count", 1)}
                  />
                </View>
              </View>
            </View>
            {!!entry && !card.ultimate && !card.type.includes("특수") && (
              <View style={styles.row}>
                <Text style={styles.muted}>
                  {t("손패")} {entry.hand}
                </Text>
                <Button
                  label="−"
                  disabled={deck.locked}
                  onPress={() => change(card, "hand", -1)}
                />
                <Button
                  label="+"
                  disabled={deck.locked}
                  onPress={() => change(card, "hand", 1)}
                />
                <Text style={styles.muted}>
                  {t("사이드")} {entry.side}
                </Text>
                <Button
                  label="−"
                  disabled={deck.locked}
                  onPress={() => change(card, "side", -1)}
                />
                <Button
                  label="+"
                  disabled={deck.locked}
                  onPress={() => change(card, "side", 1)}
                />
              </View>
            )}
          </View>
        );
      })}
    </ScrollView>
  );
}
