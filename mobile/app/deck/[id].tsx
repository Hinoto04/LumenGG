import React, { useEffect, useRef, useState } from "react";
import { View, Text, ScrollView, Pressable } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import type { Deck } from "../../src/types";
import { useApp } from "../../src/provider";
import { localized } from "../../src/core";
import {
  deckColumns,
  deckSections,
  deckDescription,
  type DeckSize,
} from "../../src/deck-display";
import { request, ApiError } from "../../src/api";
import { preference, setPreference } from "../../src/storage";
import { userMessage } from "../../src/errors";
import {
  styles,
  colors,
  Choices,
  CachedImage,
  Notice,
  Button,
} from "../../src/ui";

export default function DeckDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { catalog, language, decks, scope, user, t } = useApp();
  const [loaded, setLoaded] = useState<{
      scope: string;
      id: string;
      deck: Deck;
    } | null>(null),
    [size, setSize] = useState<DeckSize>("medium"),
    [width, setWidth] = useState(0),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [retry, setRetry] = useState(0),
    [denied, setDenied] = useState(false);
  const sizeEdited = useRef(false);
  useEffect(() => {
    preference<DeckSize>("deck-card-size", "medium").then((v) => {
      if (!sizeEdited.current && v in deckColumns) setSize(v);
    });
  }, []);
  const own = decks.find(
    (d) => !d.deleted && (String(d.id) === id || d.uuid === id),
  );
  const deck = denied
    ? null
    : loaded?.scope === scope && loaded.id === id
      ? loaded.deck
      : own;
  useEffect(() => {
    let live = true;
    setLoaded(null);
    setMessage("");
    setDenied(false);
    if (!/^\d+$/.test(id || "")) return;
    setBusy(true);
    (async () => {
      const key = `deck-view:${scope}:${id}`;
      try {
        const cached = await preference<Deck | null>(key, null);
        if (!live) return;
        if (cached) setLoaded({ scope, id, deck: cached });
        const next: Deck = await request(
          `/decks/${id}`,
          {},
          !!user,
          false,
          user?.id,
        );
        if (!live) return;
        setLoaded({ scope, id, deck: next });
        await setPreference(key, next);
      } catch (err) {
        if (!live) return;
        if (err instanceof ApiError && [403, 404].includes(err.status)) {
          setDenied(true);
          setLoaded(null);
          await setPreference(key, null);
          setMessage("덱을 볼 수 없습니다.");
        } else setMessage(userMessage(err));
      } finally {
        if (live) setBusy(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [id, scope, retry]);
  if (!deck)
    return (
      <View style={styles.screen}>
        <Notice
          text={busy ? "불러오는 중" : message || "덱을 볼 수 없습니다."}
        />
        <Button
          label="재시도"
          disabled={busy}
          onPress={() => setRetry((n) => n + 1)}
        />
      </View>
    );
  const character = catalog?.characters.find((c) => c.id === deck.character_id);
  const columns = deckColumns[size],
    gap = 4,
    tileWidth = Math.max(
      1,
      Math.floor(((width - gap * (columns - 1)) / columns) * 100) / 100,
    );
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      <Text style={styles.title}>{deck.name}</Text>
      <Text style={styles.muted}>
        {deck.author?.username || user?.username} ·{" "}
        {character ? localized(character, language) : ""} · {t(deck.visibility)}
      </Text>
      <Notice text={message} />
      <View style={{ marginTop: 16 }}>
        <Choices
          value={size}
          onChange={(v) => {
            sizeEdited.current = true;
            setSize(v as DeckSize);
            setPreference("deck-card-size", v).catch(() => undefined);
          }}
          values={[
            { key: "small", label: t("작게") },
            { key: "medium", label: t("보통") },
            { key: "large", label: t("크게") },
          ]}
        />
      </View>
      <View onLayout={(event) => setWidth(event.nativeEvent.layout.width)}>
        {deckSections(deck, catalog).map((section) => (
          <View key={section.title} style={{ marginBottom: 22 }}>
            <View style={[styles.row, { marginBottom: 10 }]}>
              <Text style={[styles.title, { marginBottom: 0, fontSize: 18 }]}>
                {t(section.title)}
              </Text>
              <Text style={styles.muted}>
                {section.tiles.length} {t("장")}
              </Text>
            </View>
            {!section.tiles.length && <Notice text="카드가 없습니다." />}
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap }}>
              {width > 0 &&
                section.tiles.map((tile, index) => (
                  <Pressable
                    key={tile.key}
                    style={{ width: tileWidth }}
                    accessibilityRole="button"
                    accessibilityLabel={`${t(section.title)} ${index + 1}: ${tile.card ? localized(tile.card, language) : `#${tile.card_id}`}`}
                    disabled={!tile.card}
                    onPress={() =>
                      router.push({
                        pathname: "/card/[id]",
                        params: { id: String(tile.card_id) },
                      })
                    }
                  >
                    {tile.card ? (
                      <CachedImage
                        url={
                          tile.card.img_mid || tile.card.img_sm || tile.card.img
                        }
                        fill
                        large={size === "large"}
                        height={tileWidth * 1.4}
                      />
                    ) : (
                      <View
                        style={{
                          height: tileWidth * 1.4,
                          backgroundColor: colors.line,
                          justifyContent: "center",
                          alignItems: "center",
                        }}
                      >
                        <Text style={styles.muted}>#{tile.card_id}</Text>
                      </View>
                    )}
                  </Pressable>
                ))}
            </View>
          </View>
        ))}
      </View>
      <View style={styles.panel}>
        <Text style={[styles.title, { fontSize: 18 }]}>{t("덱 설명")}</Text>
        <Text selectable style={[styles.text, { lineHeight: 23 }]}>
          {deckDescription(deck.description) || t("설명이 없습니다.")}
        </Text>
      </View>
    </ScrollView>
  );
}
