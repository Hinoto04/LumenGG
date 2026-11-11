import React, { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  Pressable,
  Share,
  StyleSheet,
} from "react-native";
import { useLocalSearchParams, router, Stack } from "expo-router";
import type { Deck } from "../../src/types";
import { useApp } from "../../src/provider";
import { deckIssues } from "../../src/deck-rules";
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
  Badge,
  Button,
  CachedImage,
  Chip,
  EmptyState,
  Icon,
  IconButton,
  Notice,
  Segmented,
  Skeleton,
  colors,
  radius,
  space,
  styles,
  type,
} from "../../src/ui";

export default function DeckDetail() {
  const { id, submission } = useLocalSearchParams<{
    id: string;
    submission?: string;
  }>();
  const [checkRegulation, setCheckRegulation] = useState("");
  const {
    catalog,
    language,
    decks,
    scope,
    user,
    bookmarks,
    setBookmark,
    rememberBookmarks,
    t,
  } = useApp();
  const [bookmarkBusy, setBookmarkBusy] = useState(false);
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
      : submission
        ? undefined
        : own;
  useEffect(() => {
    let live = true;
    setLoaded(null);
    setMessage("");
    setDenied(false);
    if (!/^\d+$/.test(id || "")) return;
    setBusy(true);
    (async () => {
      const key = `deck-view:${scope}:${id}:${submission || ""}`;
      try {
        const cached = await preference<Deck | null>(key, null);
        if (!live) return;
        if (cached) setLoaded({ scope, id, deck: cached });
        const next: Deck = await request(
          submission ? `/submitted-decks/${submission}` : `/decks/${id}`,
          {},
          !!user,
          false,
          user?.id,
        );
        if (!live) return;
        setLoaded({ scope, id, deck: next });
        if (user && !submission) void rememberBookmarks([next]);
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
  }, [id, submission, scope, retry]);
  if (!deck)
    return (
      <View style={styles.screen}>
        {busy ? (
          <View style={{ gap: space.md }}>
            <Skeleton height={120} rounded={radius.lg} />
            <Skeleton height={44} />
            <Skeleton height={260} rounded={radius.lg} />
          </View>
        ) : (
          <EmptyState
            icon="lock-closed-outline"
            title={message || "덱을 볼 수 없습니다."}
            action={{
              label: "재시도",
              icon: "refresh",
              onPress: () => setRetry((n) => n + 1),
            }}
          />
        )}
      </View>
    );
  const displayCatalog =
    catalog && deck.snapshot_catalog
      ? {
          ...catalog,
          cards: Object.values(deck.snapshot_catalog).map((c: any) => ({
            ...c,
            localized: { ko: { name: c.name, text: c.text } },
          })),
        }
      : catalog;
  const checked =
    checkRegulation && catalog
      ? deckIssues(
          {
            ...deck,
            regulation_version_id: Number(checkRegulation),
            regulation_rules: catalog.rules.regulations?.find(
              (v) => v.id === Number(checkRegulation),
            )?.rules,
          },
          catalog,
        )
      : null;
  const character = catalog?.characters.find((c) => c.id === deck.character_id);
  // 세로 폭(약 380dp)에서의 칸 수를 기준으로, 넓은 화면에서는 같은 칸 크기로 칸 수를 늘린다.
  const columns = Math.max(
      deckColumns[size],
      Math.round((deckColumns[size] * width) / 380),
    ),
    gap = 4,
    tileWidth = Math.max(
      1,
      Math.floor(((width - gap * (columns - 1)) / columns) * 100) / 100,
    );
  const total = deck.cards.reduce((n, e) => n + e.count, 0);
  const reserveTotal = (deck.reserve_cards || []).reduce(
    (n, e) => n + e.count,
    0,
  );
  const judged = deck.validation?.is_valid;
  // 북마크는 서버에 올라간 덱만, 로그인했을 때 걸 수 있다(대회 제출본 제외).
  const deckId = deck.id;
  const canBookmark = !!user && !!deckId && !submission;
  const bookmarked = !!deckId && bookmarks.includes(deckId);
  const toggleBookmark = async () => {
    if (!deckId || bookmarkBusy) return;
    setBookmarkBusy(true);
    try {
      const next = await setBookmark(deckId, !bookmarked);
      setMessage(next ? "북마크했습니다." : "북마크를 해제했습니다.");
    } catch (err) {
      setMessage(userMessage(err));
    } finally {
      setBookmarkBusy(false);
    }
  };
  const shareDeck = () => {
    void Share.share({
      message: JSON.stringify({
        ...deck,
        schema_version: 2,
        id: undefined,
        uuid: undefined,
        author: undefined,
        locked: undefined,
      }),
    });
  };
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 48 }}
    >
      <Stack.Screen options={{ title: deck.name }} />
      <View style={detailStyles.hero}>
        <View style={detailStyles.portrait}>
          {character ? (
            <CachedImage
              url={character.img_sm || character.img}
              height={112}
              fill
            />
          ) : (
            <Icon name="person-outline" size={32} color={colors.subtle} />
          )}
        </View>
        <View style={{ flex: 1, gap: 6 }}>
          <Text style={type.title} numberOfLines={2}>
            {deck.name}
          </Text>
          <Text style={styles.muted} numberOfLines={1}>
            {(character ? localized(character, language) : "") +
              " · " +
              (deck.author?.username || user?.username || "")}
          </Text>
          <View style={detailStyles.badges}>
            <Badge label={total + " " + t("장")} />
            {reserveTotal > 0 && (
              <Badge label={t("교체 덱") + " " + reserveTotal} />
            )}
            <Badge
              label={deck.visibility}
              tone={
                deck.visibility === "public"
                  ? "success"
                  : deck.visibility === "unlisted"
                    ? "accent"
                    : "neutral"
              }
            />
            {!!submission && (
              <Badge
                label={
                  t("대회 당시 판정") +
                  " · " +
                  t(
                    judged === true
                      ? "적합"
                      : judged === false
                        ? "위반"
                        : "미검사",
                  )
                }
                tone={
                  judged === true
                    ? "success"
                    : judged === false
                      ? "danger"
                      : "neutral"
                }
              />
            )}
          </View>
        </View>
      </View>
      <Notice text={message} />
      <View style={detailStyles.actions}>
        {!!own && !deck.locked && (
          <Button
            label="덱 수정"
            icon="create-outline"
            variant="primary"
            style={{ flex: 1 }}
            onPress={() =>
              router.push({
                pathname: "/deck-editor",
                params: { id: deck.uuid },
              })
            }
          />
        )}
        <Button
          label="복사해서 편집"
          icon="copy-outline"
          style={{ flex: 1 }}
          onPress={() =>
            router.push({
              pathname: "/deck-editor",
              params: {
                copy: submission
                  ? `submission:${submission}`
                  : String(deck.id || deck.uuid),
              },
            })
          }
        />
        {canBookmark && (
          <IconButton
            icon={bookmarked ? "bookmark" : "bookmark-outline"}
            label={bookmarked ? "북마크 해제" : "북마크"}
            filled
            disabled={bookmarkBusy}
            onPress={toggleBookmark}
          />
        )}
        <IconButton
          icon="share-social-outline"
          label="덱 코드 공유"
          filled
          onPress={shareDeck}
        />
      </View>

      {!!catalog?.rules.regulations?.length && (
        <>
          <Text style={detailStyles.heading}>{t("다른 규정으로 확인")}</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ gap: space.sm }}
            style={{ flexGrow: 0 }}
          >
            <Chip
              label="확인 안 함"
              selected={!checkRegulation}
              onPress={() => setCheckRegulation("")}
            />
            {catalog.rules.regulations.map((v) => (
              <Chip
                key={v.id}
                label={v.name + " / " + v.version}
                selected={checkRegulation === String(v.id)}
                onPress={() => setCheckRegulation(String(v.id))}
              />
            ))}
          </ScrollView>
        </>
      )}
      {!!checked && (
        <View
          style={[
            detailStyles.check,
            checked.length ? detailStyles.checkBad : detailStyles.checkGood,
          ]}
        >
          {checked.length ? (
            checked.map((issue, n) => (
              <View key={n} style={detailStyles.issue}>
                <Icon name="alert-circle" size={16} color={colors.danger} />
                <Text style={[styles.text, { flex: 1, fontSize: 14 }]}>
                  {t(issue.message)}
                </Text>
              </View>
            ))
          ) : (
            <View style={detailStyles.issue}>
              <Icon name="checkmark-circle" size={16} color={colors.success} />
              <Text style={[styles.text, { flex: 1, fontSize: 14 }]}>
                {t("선택한 규정에 적합한 구성입니다.")}
              </Text>
            </View>
          )}
        </View>
      )}

      <View style={detailStyles.sizeRow}>
        <Text
          style={[
            detailStyles.heading,
            { marginTop: 0, marginBottom: 0, flex: 1 },
          ]}
        >
          {t("카드 구성")}
        </Text>
        <View style={{ width: 168 }}>
          <Segmented
            value={size}
            onChange={(v) => {
              sizeEdited.current = true;
              setSize(v as DeckSize);
              setPreference("deck-card-size", v).catch(() => undefined);
            }}
            values={[
              { key: "small", label: "작게" },
              { key: "medium", label: "보통" },
              { key: "large", label: "크게" },
            ]}
          />
        </View>
      </View>
      <View onLayout={(event) => setWidth(event.nativeEvent.layout.width)}>
        {deckSections(deck, displayCatalog).map((section) => (
          <View key={section.title} style={{ marginBottom: space.xl }}>
            <View style={detailStyles.sectionHeader}>
              <Text style={type.heading}>{t(section.title)}</Text>
              <Badge label={String(section.tiles.length)} tone="accent" />
            </View>
            {!section.tiles.length && <Notice text="카드가 없습니다." />}
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap }}>
              {width > 0 &&
                section.tiles.map((tile, index) => (
                  <Pressable
                    key={tile.key}
                    style={({ pressed }) => [
                      { width: tileWidth, borderRadius: 6, overflow: "hidden" },
                      pressed && { opacity: 0.8 },
                    ]}
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
                          backgroundColor: colors.surface2,
                          justifyContent: "center",
                          alignItems: "center",
                        }}
                      >
                        <Icon name="help" size={16} color={colors.subtle} />
                        <Text style={styles.muted}>#{tile.card_id}</Text>
                      </View>
                    )}
                  </Pressable>
                ))}
            </View>
          </View>
        ))}
      </View>
      <Text style={detailStyles.heading}>{t("덱 설명")}</Text>
      <View style={styles.panel}>
        <Text selectable style={[styles.text, { lineHeight: 23 }]}>
          {deckDescription(deck.description) || t("설명이 없습니다.")}
        </Text>
      </View>
    </ScrollView>
  );
}

const detailStyles = StyleSheet.create({
  hero: {
    flexDirection: "row",
    gap: space.lg,
    alignItems: "center",
    padding: space.md,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  portrait: {
    width: 80,
    height: 112,
    borderRadius: radius.md,
    overflow: "hidden",
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  actions: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    marginTop: space.md,
  },
  heading: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    marginTop: space.xl,
    marginBottom: space.sm,
    marginLeft: space.xs,
  },
  check: {
    marginTop: space.md,
    padding: space.md,
    gap: space.sm,
    borderRadius: radius.md,
    borderWidth: 1,
  },
  checkBad: { borderColor: colors.danger, backgroundColor: colors.dangerSoft },
  checkGood: {
    borderColor: colors.success,
    backgroundColor: "rgba(127, 209, 166, 0.10)",
  },
  issue: { flexDirection: "row", gap: space.sm, alignItems: "flex-start" },
  sizeRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: space.xl,
    marginBottom: -space.xs,
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    marginBottom: space.sm,
  },
});
