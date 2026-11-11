import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  Easing,
  FlatList,
  type GestureResponderEvent,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  Stack,
  router,
  useLocalSearchParams,
  useFocusEffect,
} from "expo-router";
import * as Crypto from "expo-crypto";
import { useApp } from "../src/provider";
import { localized, normalizeSearch } from "../src/core";
import {
  copyAvailability,
  deckIssues,
  deckStats,
  isTrait,
} from "../src/deck-rules";
import {
  DECK_ZONES,
  type DeckZone,
  addCopy,
  isMovable,
  moveCopy,
  removeCopy,
} from "../src/deck-edit";
import { deckSections } from "../src/deck-display";
import { importDeckCode } from "../src/deck-exchange";
import { sortCards } from "../src/card-search";
import { cardImageFor, columnsFor } from "../src/layout";
import { CharacterGrid } from "../src/character-picker";
import { request } from "../src/api";
import { preference, setPreference } from "../src/storage";
import { userMessage } from "../src/errors";
import type { Card, Catalog, Deck, RegulationVersion } from "../src/types";
import {
  Badge,
  Button,
  CachedImage,
  Chip,
  EmptyState,
  Icon,
  type IconName,
  Input,
  Notice,
  SearchInput,
  Segmented,
  Skeleton,
  colors,
  radius,
  space,
  styles,
  tapFeedback,
} from "../src/ui";

const NEUTRAL_CHARACTER_ID = 1;
const KIMERA_CHARACTER_ID = 15;
const CARD_RATIO = 1.4;

/** 아래 탭 순서. 화면도 이 순서로 가로로 이어져 있어 스와이프로 오간다. */
const TABS: { key: string; label: string; icon: IconName }[] = [
  { key: "search", label: "카드 검색", icon: "search-outline" },
  { key: "list", label: "덱리스트", icon: "albums-outline" },
  { key: "info", label: "덱 정보", icon: "information-circle-outline" },
];
const SEARCH = 0,
  LIST = 1,
  INFO = 2;

const ZONE_LABEL: Record<DeckZone, string> = {
  list: "리스트",
  hand: "손패",
  side: "사이드",
};

/** 키메라는 다른 캐릭터의 공격 기술을 덱에 넣을 수 있다. */
function usableBy(card: Card, characterId: number) {
  if (card.character_id === NEUTRAL_CHARACTER_ID) return true;
  if (card.character_id === characterId) return true;
  return (
    characterId === KIMERA_CHARACTER_ID &&
    !card.ultimate &&
    !isTrait(card) &&
    card.type.includes("공격")
  );
}

interface Flyer {
  key: number;
  url: string;
  x: number;
  y: number;
  width: number;
  progress: Animated.Value;
}

export default function DeckEditor() {
  const params = useLocalSearchParams<{ id?: string; copy?: string }>();
  const { catalog, decks, user, scope, saveDeck, t } = useApp();
  const [loadedScope, setLoadedScope] = useState(scope);
  const [deck, setDeck] = useState<Deck | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [versions, setVersions] = useState<RegulationVersion[]>([]);
  const [tab, setTab] = useState(INFO);
  const [pager, setPager] = useState({ width: 0, height: 0 });
  const [dragging, setDragging] = useState(false);
  const [flyers, setFlyers] = useState<Flyer[]>([]);
  // 헤더 매수 칸을 눌렀을 때 보여 주는 설명.
  const [guide, setGuide] = useState<"own" | "total" | null>(null);
  const pagerRef = useRef<ScrollView>(null);
  const rootRef = useRef<View>(null);
  const tabRef = useRef(tab);
  tabRef.current = tab;
  const listPulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!catalog) return;
    let live = true;
    setDeck(null);
    setError("");
    (async () => {
      const id = params.id || params.copy;
      const source = id
        ? decks.find((d) => d.uuid === id || String(d.id) === id) ||
          (await request(
            id.startsWith("submission:")
              ? `/submitted-decks/${id.split(":")[1]}`
              : `/decks/${id}`,
            {},
            !!user,
          ))
        : null;
      if (!live) return;
      // 새 덱은 캐릭터를 비워 두고 덱 정보 탭에서 먼저 고르게 한다.
      const initial: Deck = source
        ? { ...source }
        : {
            uuid: Crypto.randomUUID(),
            name: "새 덱",
            character_id: 0,
            description: "",
            keyword: "",
            tags: "",
            visibility: "private",
            cards: [],
            reserve_cards: [],
          };
      if (params.copy) {
        delete initial.id;
        initial.uuid = Crypto.randomUUID();
        initial.locked = false;
        initial.author = user || undefined;
        initial.name += " 복사본";
      }
      if (initial.locked)
        throw new Error("대회 제출 덱은 복사한 뒤 편집해주세요.");
      initial.schema_version = 2;
      initial.reserve_cards ||= [];
      const traits = catalog.characters.find(
        (c) => c.id === initial.character_id,
      )?.traits;
      if (!initial.trait_card_id && traits?.length === 1)
        initial.trait_card_id = traits[0]!.id;
      setDeck(initial);
      setTab(source ? LIST : INFO);
      setLoadedScope(scope);
      const cached = await preference<RegulationVersion[]>(
        `regulations:${scope}`,
        catalog.rules.regulations || [],
      );
      if (live)
        setVersions(
          initial.regulation &&
            !cached.some((v) => v.id === initial.regulation!.id)
            ? [...cached, initial.regulation]
            : cached,
        );
      try {
        const response = await request("/regulations", {}, !!user);
        if (live)
          setVersions(
            initial.regulation &&
              !response.versions.some(
                (v: any) => v.id === initial.regulation!.id,
              )
              ? [...response.versions, initial.regulation]
              : response.versions,
          );
        await setPreference(`regulations:${scope}`, response.versions);
      } catch {}
    })().catch((e) => live && setError(userMessage(e)));
    return () => {
      live = false;
    };
  }, [catalog, params.id, params.copy, scope]);
  useFocusEffect(
    React.useCallback(() => {
      let live = true;
      request("/regulations", {}, !!user)
        .then((result) => {
          if (live)
            setVersions((previous) => [
              ...result.versions,
              ...previous.filter(
                (v) => !result.versions.some((r: any) => r.id === v.id),
              ),
            ]);
          return setPreference(`regulations:${scope}`, result.versions);
        })
        .catch(() => {});
      return () => {
        live = false;
      };
    }, [scope, user?.id]),
  );
  const ready = !!catalog && !!deck && loadedScope === scope;
  // 세 화면이 다 그려진 뒤의 폭. 이 폭에 맞춰 현재 탭 위치로 옮기기 전에는 스크롤로 탭을 바꾸지 않는다.
  const positioned = useRef(0);
  // 탭을 눌러 옮기는 중인 목적지. 옮기는 동안 지나가는 화면으로 탭 표시가 바뀌지 않게 한다.
  const heading = useRef<number | null>(null);
  if (!ready)
    return (
      <View style={styles.screen}>
        {error ? (
          <EmptyState icon="alert-circle-outline" title={error} />
        ) : (
          <View style={{ gap: space.md }}>
            <Skeleton height={48} />
            <Skeleton height={180} rounded={radius.lg} />
            <Skeleton height={120} rounded={radius.lg} />
          </View>
        )}
      </View>
    );
  const current = deck!,
    data = catalog!;
  // 같은 문구의 항목(예: 등록 특성과 사용 특성 확인)은 한 번만 보여 준다.
  const issues = deckIssues(current, data, "draft").filter(
    (issue, index, all) =>
      all.findIndex((other) => other.message === issue.message) === index,
  );
  const errors = issues.filter((i) => i.severity === "error");
  const total = current.cards.reduce((n, e) => n + e.count, 0);
  const change = (patch: Partial<Deck>) =>
    setDeck((previous) => (previous ? { ...previous, ...patch } : previous));
  const goTo = (index: number, animated = true) => {
    heading.current = animated ? index : null;
    setTab(index);
    pagerRef.current?.scrollTo({ x: index * pager.width, animated });
  };
  const stats = deckStats(current, data);
  const range =
    stats.minimum === stats.maximum
      ? String(stats.minimum)
      : `${stats.minimum}~${stats.maximum}`;
  const meters = {
    own: {
      value: `${stats.own}/${stats.ownMinimum}`,
      ok: stats.own >= stats.ownMinimum,
      title: "캐릭터 마크 기술",
      detail: `${t("현재")} ${stats.own} · ${t("최소")} ${stats.ownMinimum}`,
    },
    total: {
      value: `${stats.total}/${range}`,
      ok: stats.total >= stats.minimum && stats.total <= stats.maximum,
      title: "기술 카드 전체",
      detail: `${t("현재")} ${stats.total} · ${t("필요")} ${range} (${t("얼티밋 제외")})`,
    },
  };
  const missing = !current.character_id
    ? INFO
    : !current.name.trim()
      ? INFO
      : errors.length > 0
        ? LIST
        : -1;
  const save = async () => {
    if (missing >= 0 || data.schema_version !== 2) {
      tapFeedback("warning");
      if (missing >= 0) goTo(missing);
      return;
    }
    setBusy(true);
    try {
      await saveDeck(current);
      router.replace({
        pathname: "/deck/[id]",
        params: { id: current.uuid },
      });
    } catch (e) {
      setError(userMessage(e));
    } finally {
      setBusy(false);
    }
  };
  /** 검색에서 누른 카드가 덱리스트(오른쪽 화면) 쪽으로 날아가는 연출. */
  const fly = (url: string, page: { x: number; y: number; width: number }) => {
    rootRef.current?.measure((_x, _y, _w, _h, rootX, rootY) => {
      const flyer: Flyer = {
        key: Date.now() + Math.random(),
        url,
        x: page.x - rootX,
        y: page.y - rootY,
        width: page.width,
        progress: new Animated.Value(0),
      };
      setFlyers((list) => [...list, flyer]);
      Animated.timing(flyer.progress, {
        toValue: 1,
        duration: 420,
        easing: Easing.in(Easing.cubic),
        useNativeDriver: true,
      }).start(() => {
        setFlyers((list) => list.filter((f) => f.key !== flyer.key));
        listPulse.setValue(1);
        Animated.spring(listPulse, {
          toValue: 0,
          friction: 4,
          useNativeDriver: true,
        }).start();
      });
    });
  };
  const addCard = (card: Card) => {
    // 연속으로 눌러도 매수 제한을 넘지 않게 최신 덱으로 다시 확인한다.
    setDeck((previous) =>
      previous && copyAvailability(previous, data)(card) > 0
        ? { ...previous, cards: addCopy(previous.cards, card) }
        : previous,
    );
  };
  return (
    <View ref={rootRef} style={{ flex: 1, backgroundColor: colors.bg }}>
      <Stack.Screen
        options={{
          headerRight: () => (
            <View style={editorStyles.headerRight}>
              {current.character_id > 0 &&
                (["own", "total"] as const).map((key) => {
                  const meter = meters[key];
                  return (
                    <Pressable
                      key={key}
                      accessibilityRole="button"
                      accessibilityLabel={t(meter.title) + " " + meter.value}
                      onPress={() =>
                        setGuide((previous) => (previous === key ? null : key))
                      }
                      hitSlop={4}
                      style={[
                        editorStyles.meter,
                        {
                          backgroundColor: meter.ok
                            ? colors.accentSoft
                            : colors.dangerSoft,
                          borderColor: meter.ok ? colors.accent : colors.danger,
                        },
                      ]}
                    >
                      <Text
                        style={[
                          editorStyles.meterText,
                          { color: meter.ok ? colors.accent : colors.danger },
                        ]}
                      >
                        {meter.value}
                      </Text>
                    </Pressable>
                  );
                })}
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t("저장")}
                accessibilityState={{ disabled: missing >= 0, busy }}
                disabled={busy}
                onPress={save}
                hitSlop={8}
                style={({ pressed }) => [
                  editorStyles.save,
                  missing >= 0 && editorStyles.saveBlocked,
                  pressed && { opacity: 0.7 },
                ]}
              >
                <Icon
                  name="save-outline"
                  size={16}
                  color={missing >= 0 ? colors.subtle : colors.onAccent}
                />
                <Text
                  style={[
                    editorStyles.saveText,
                    missing >= 0 && { color: colors.subtle },
                  ]}
                >
                  {busy ? t("저장 중") : t("저장")}
                </Text>
              </Pressable>
            </View>
          ),
        }}
      />
      {(!!error || data.schema_version !== 2) && (
        <View style={{ paddingHorizontal: space.lg, paddingTop: space.sm }}>
          <Notice text={error} />
          {data.schema_version !== 2 && (
            <Notice text="특성·규정 데이터를 업데이트한 뒤 새 형식으로 저장해주세요." />
          )}
        </View>
      )}
      <ScrollView
        ref={pagerRef}
        horizontal
        pagingEnabled
        scrollEnabled={!dragging}
        showsHorizontalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        scrollEventThrottle={32}
        style={{ flex: 1 }}
        onLayout={(e) => {
          const { width, height } = e.nativeEvent.layout;
          if (width !== pager.width || height !== pager.height)
            setPager({ width, height });
        }}
        onContentSizeChange={(contentWidth) => {
          // 처음 열 때와 화면 폭이 바뀔 때(회전) 현재 탭 위치로 맞춘다.
          // 막 그려진 직후에는 scrollTo가 무시될 수 있어, 실제로 그 위치에 간 것을
          // onScroll에서 확인한 뒤에 위치를 확정한다.
          const width = pager.width;
          if (
            !width ||
            positioned.current === width ||
            contentWidth < width * TABS.length
          )
            return;
          const target = tabRef.current;
          if (target === 0) {
            positioned.current = width;
            return;
          }
          heading.current = target;
          const jump = () => {
            if (positioned.current === width) return;
            pagerRef.current?.scrollTo({ x: target * width, animated: false });
          };
          requestAnimationFrame(jump);
          setTimeout(jump, 120);
          setTimeout(jump, 400);
        }}
        onScroll={(e) => {
          if (!pager.width) return;
          const x = e.nativeEvent.contentOffset.x;
          if (heading.current !== null) {
            if (Math.abs(x - heading.current * pager.width) < 2) {
              heading.current = null;
              positioned.current = pager.width;
            }
            return;
          }
          if (positioned.current !== pager.width) return;
          const index = Math.round(x / pager.width);
          if (index !== tabRef.current && index >= 0 && index < TABS.length)
            setTab(index);
        }}
        onMomentumScrollEnd={(e) => {
          // 스크롤이 멈춘 위치가 최종 탭이다(마지막 onScroll이 빠지는 경우 대비).
          if (!pager.width || positioned.current !== pager.width) return;
          heading.current = null;
          const index = Math.round(e.nativeEvent.contentOffset.x / pager.width);
          if (index >= 0 && index < TABS.length) setTab(index);
        }}
      >
        {pager.width > 0 && (
          <>
            <View style={{ width: pager.width, height: pager.height }}>
              <MemoSearchPage
                deck={current}
                catalog={data}
                width={pager.width}
                onAdd={(card, from) => {
                  addCard(card);
                  tapFeedback("light");
                  fly(cardImageFor(card, from.width), from);
                }}
                onPickCharacter={() => goTo(INFO)}
              />
            </View>
            <View style={{ width: pager.width, height: pager.height }}>
              <MemoListPage
                deck={current}
                catalog={data}
                width={pager.width}
                height={pager.height}
                onChangeCards={(cards) => change({ cards })}
                onDragging={setDragging}
              />
            </View>
            <View style={{ width: pager.width, height: pager.height }}>
              <MemoInfoPage
                deck={current}
                catalog={data}
                width={pager.width}
                versions={versions}
                issues={issues}
                onChange={change}
                onImport={(imported) => {
                  setDeck(imported);
                  if (imported.regulation)
                    setVersions((previous) => [
                      ...previous.filter(
                        (v) => v.id !== imported.regulation!.id,
                      ),
                      imported.regulation!,
                    ]);
                }}
                onError={setError}
              />
            </View>
          </>
        )}
      </ScrollView>
      <View style={editorStyles.tabs} accessibilityRole="tablist">
        {TABS.map((item, index) => {
          const selected = tab === index;
          const badge =
            index === LIST
              ? String(total)
              : index === INFO && !current.character_id
                ? "!"
                : "";
          return (
            <Pressable
              key={item.key}
              accessibilityRole="tab"
              accessibilityState={{ selected }}
              accessibilityLabel={t(item.label)}
              onPress={() => {
                if (!selected) tapFeedback("selection");
                goTo(index);
              }}
              style={({ pressed }) => [
                editorStyles.tab,
                pressed && { backgroundColor: colors.surface2 },
              ]}
            >
              <View
                style={[
                  editorStyles.tabIndicator,
                  selected && { backgroundColor: colors.accent },
                ]}
              />
              <Animated.View
                style={[
                  editorStyles.tabInner,
                  index === LIST && {
                    transform: [
                      {
                        scale: listPulse.interpolate({
                          inputRange: [0, 1],
                          outputRange: [1, 1.18],
                        }),
                      },
                    ],
                  },
                ]}
              >
                <Icon
                  name={item.icon}
                  size={20}
                  color={selected ? colors.accent : colors.muted}
                />
                <Text
                  numberOfLines={1}
                  style={[
                    editorStyles.tabLabel,
                    selected && { color: colors.accent },
                  ]}
                >
                  {t(item.label)}
                </Text>
                {!!badge && (
                  <View
                    style={[
                      editorStyles.tabBadge,
                      (badge === "!" ||
                        (index === LIST && errors.length > 0)) && {
                        backgroundColor: colors.danger,
                      },
                    ]}
                  >
                    <Text style={editorStyles.tabBadgeText}>{badge}</Text>
                  </View>
                )}
              </Animated.View>
            </Pressable>
          );
        })}
      </View>
      {guide && (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("닫기")}
          onPress={() => setGuide(null)}
          style={StyleSheet.absoluteFill}
        >
          <View style={editorStyles.guide}>
            <Text style={editorStyles.guideTitle}>
              {t(meters[guide].title) + "  " + meters[guide].value}
            </Text>
            <Text style={editorStyles.guideText}>{meters[guide].detail}</Text>
            <Text style={[editorStyles.guideText, { color: colors.subtle }]}>
              {meters[guide].ok
                ? t("노란색: 조건을 만족합니다.")
                : t("빨간색: 조건을 만족하지 않습니다.")}
            </Text>
          </View>
        </Pressable>
      )}
      {flyers.map((f) => (
        <Animated.View
          key={f.key}
          pointerEvents="none"
          style={{
            position: "absolute",
            left: f.x,
            top: f.y,
            width: f.width,
            opacity: f.progress.interpolate({
              inputRange: [0, 0.7, 1],
              outputRange: [1, 0.95, 0],
            }),
            transform: [
              {
                translateX: f.progress.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0, pager.width - f.x + f.width * 0.2],
                }),
              },
              {
                translateY: f.progress.interpolate({
                  inputRange: [0, 0.4, 1],
                  outputRange: [0, -24, 40],
                }),
              },
              {
                scale: f.progress.interpolate({
                  inputRange: [0, 0.25, 1],
                  outputRange: [1, 1.08, 0.55],
                }),
              },
              {
                rotate: f.progress.interpolate({
                  inputRange: [0, 1],
                  outputRange: ["0deg", "14deg"],
                }),
              },
            ],
          }}
        >
          <CachedImage url={f.url} fill height={f.width * CARD_RATIO} />
        </Animated.View>
      ))}
    </View>
  );
}

// 세 화면은 덱·카탈로그·크기가 바뀔 때만 다시 그린다. 카드가 날아가는 연출이나 드래그 상태가
// 바뀔 때마다 모두 다시 그리면 느린 기기에서 탭이 빠지거나 드래그보다 스와이프가 먼저 잡힌다.
// 함수 속성은 모두 함수형 setState를 쓰거나 비교하는 값에서만 달라지므로 비교에서 뺀다.
const MemoSearchPage = React.memo(
  (props: React.ComponentProps<typeof SearchPage>) => <SearchPage {...props} />,
  (a, b) => a.deck === b.deck && a.catalog === b.catalog && a.width === b.width,
);
const MemoListPage = React.memo(
  (props: React.ComponentProps<typeof ListPage>) => <ListPage {...props} />,
  (a, b) =>
    a.deck === b.deck &&
    a.catalog === b.catalog &&
    a.width === b.width &&
    a.height === b.height,
);
const MemoInfoPage = React.memo(
  (props: React.ComponentProps<typeof InfoPage>) => <InfoPage {...props} />,
  (a, b) =>
    a.deck === b.deck &&
    a.catalog === b.catalog &&
    a.width === b.width &&
    a.versions === b.versions,
);

// ── 카드 검색 ────────────────────────────────────────────────

const TYPE_FILTERS = [
  { key: "", label: "전체" },
  { key: "공격", label: "공격" },
  { key: "수비", label: "수비" },
  { key: "특수", label: "특수" },
  { key: "ultimate", label: "얼티밋" },
];

function SearchPage({
  deck,
  catalog,
  width,
  onAdd,
  onPickCharacter,
}: {
  deck: Deck;
  catalog: Catalog;
  width: number;
  onAdd: (card: Card, from: { x: number; y: number; width: number }) => void;
  onPickCharacter: () => void;
}) {
  const { language, t } = useApp();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const sorted = useMemo(
    () =>
      sortCards(
        catalog.cards.filter((c) => c.type !== "토큰" && !isTrait(c)),
        "code_asc",
        language,
        catalog,
      ),
    [catalog, language],
  );
  const available = useMemo(
    () => copyAvailability(deck, catalog),
    [deck.cards, deck.character_id, deck.trait_card_id, catalog],
  );
  if (!deck.character_id)
    return (
      <EmptyState
        icon="person-circle-outline"
        title="캐릭터를 먼저 선택해주세요."
        description="덱 정보에서 캐릭터를 고르면 그 캐릭터가 쓸 수 있는 카드만 보여 줍니다."
        action={{
          label: "덱 정보로",
          icon: "arrow-forward",
          onPress: onPickCharacter,
        }}
      />
    );
  const needle = normalizeSearch(query);
  const counts = new Map(deck.cards.map((e) => [e.card_id, e.count]));
  // 매수 제한만큼 넣은 카드는 결과에서 빼서 같은 카드를 더 넣지 못하게 한다.
  const results = sorted.filter(
    (c) =>
      usableBy(c, deck.character_id) &&
      (!kind ||
        (kind === "ultimate"
          ? c.ultimate
          : !c.ultimate && c.type.includes(kind))) &&
      (!needle ||
        (
          c.search || normalizeSearch(`${localized(c, language)} ${c.code}`)
        ).includes(needle)) &&
      available(c) > 0,
  );
  const gap = space.sm;
  const inner = width - space.lg * 2;
  const columns = columnsFor(inner, 88, 3, 8);
  const tileWidth = (inner - gap * (columns - 1)) / columns;
  return (
    <View style={{ flex: 1 }}>
      <View style={{ paddingHorizontal: space.lg, paddingTop: space.md }}>
        <SearchInput
          accessibilityLabel={t("추가할 카드 검색")}
          placeholder="카드명·번호 검색"
          value={query}
          onChangeText={setQuery}
        />
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ gap: space.sm }}
          style={{ flexGrow: 0, marginBottom: space.sm }}
        >
          {TYPE_FILTERS.map((f) => (
            <Chip
              key={f.key}
              label={f.label}
              selected={kind === f.key}
              onPress={() => setKind(f.key)}
            />
          ))}
        </ScrollView>
      </View>
      <FlatList
        key={columns}
        data={results}
        numColumns={columns}
        keyExtractor={(c) => String(c.id)}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        columnWrapperStyle={columns > 1 ? { gap } : undefined}
        contentContainerStyle={{
          paddingHorizontal: space.lg,
          paddingBottom: space.xl,
        }}
        initialNumToRender={16}
        windowSize={7}
        ListHeaderComponent={
          <Text style={[styles.muted, { marginBottom: space.sm }]}>
            {t("눌러서 리스트에 넣습니다. 특수 기술은 사이드로 들어갑니다.")}
          </Text>
        }
        ListEmptyComponent={
          <EmptyState icon="search-outline" title="검색 결과가 없습니다." />
        }
        renderItem={({ item }) => (
          <SearchTile
            card={item}
            width={tileWidth}
            count={counts.get(item.id) || 0}
            onAdd={onAdd}
          />
        )}
      />
    </View>
  );
}

function SearchTile({
  card,
  width,
  count,
  onAdd,
}: {
  card: Card;
  width: number;
  count: number;
  onAdd: (card: Card, from: { x: number; y: number; width: number }) => void;
}) {
  const { language, t } = useApp();
  const name = localized(card, language);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={name + " " + t("추가")}
      accessibilityHint={t("길게 누르면 카드 정보를 봅니다.")}
      onPress={(e) => {
        // 누른 지점에서 타일의 시작 위치를 구한다. 넣은 카드는 결과에서 바로 빠질 수 있어
        // 비동기 측정 대신 터치 좌표를 쓴다.
        const { pageX, pageY, locationX, locationY } = e.nativeEvent;
        onAdd(card, { x: pageX - locationX, y: pageY - locationY, width });
      }}
      onLongPress={() =>
        router.push({ pathname: "/card/[id]", params: { id: card.id } })
      }
      delayLongPress={350}
      style={({ pressed }) => [
        { width, marginBottom: space.md },
        pressed && { opacity: 0.8, transform: [{ scale: 0.96 }] },
      ]}
    >
      <View>
        <CachedImage
          url={cardImageFor(card, width)}
          fill
          height={width * CARD_RATIO}
        />
        {count > 0 && (
          <View style={editorStyles.countBadge}>
            <Text style={editorStyles.countBadgeText}>{"×" + count}</Text>
          </View>
        )}
      </View>
      <Text numberOfLines={1} style={editorStyles.tileName}>
        {name}
      </Text>
    </Pressable>
  );
}

// ── 덱리스트 ─────────────────────────────────────────────────

interface ZoneTile {
  card_id: number;
  card?: Card;
  key: string;
}
interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}
interface Drag {
  tile: ZoneTile;
  zone: DeckZone;
}

function ListPage({
  deck,
  catalog,
  width,
  height,
  onChangeCards,
  onDragging,
}: {
  deck: Deck;
  catalog: Catalog;
  width: number;
  height: number;
  onChangeCards: (cards: Deck["cards"]) => void;
  onDragging: (value: boolean) => void;
}) {
  const { language, t } = useApp();
  const [selected, setSelected] = useState<Drag | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [hover, setHover] = useState<DeckZone | null>(null);
  const [zoneHeights, setZoneHeights] = useState<
    Partial<Record<DeckZone, number>>
  >({});
  const ghost = useRef(new Animated.ValueXY()).current;
  const pageRef = useRef<View>(null);
  const sections = deckSections(deck, catalog);
  const tiles: Record<DeckZone, ZoneTile[]> = {
    list: sections[0]!.tiles,
    hand: sections[1]!.tiles,
    side: sections[2]!.tiles,
  };
  const stats = deckStats(deck, catalog);
  // 영역 오른쪽 아래에 붙는 영역명·매수. 리스트·손패는 시작 배치 기준과 맞는지 색으로 보여 준다.
  const counters: Record<DeckZone, { value: string; ok: boolean }> = {
    list: {
      value: `${stats.list}/${stats.listTarget}`,
      ok: stats.list === stats.listTarget,
    },
    hand: {
      value: `${stats.hand}/${stats.handTarget}`,
      ok: stats.hand === stats.handTarget,
    },
    side: { value: String(tiles.side.length), ok: true },
  };

  // 페이지 높이 안에 세 영역이 스크롤 없이 들어가는 가장 큰 카드 크기를 고른다.
  // 각 영역의 마지막 줄 오른쪽 끝 한 칸은 영역명·매수 표시 자리로 비워 둔다.
  const gap = 4;
  const pad = space.md;
  const zonePad = space.sm;
  const zoneGap = space.sm;
  // 화면 여백, 영역 안쪽 여백, 영역 테두리(1px × 2)를 뺀 폭과 높이.
  const inner = width - pad * 2 - zonePad * 2 - 2;
  const available = height - pad * 2 - zoneGap * 2 - 3 * (zonePad * 2 + 2);
  const rowsFor = (columns: number) =>
    DECK_ZONES.map((zone) =>
      Math.max(1, Math.ceil(tiles[zone].length / columns)),
    );
  const heightFor = (tileWidth: number, columns: number) =>
    rowsFor(columns).reduce(
      (sum, rows) => sum + rows * tileWidth * CARD_RATIO + (rows - 1) * gap,
      0,
    );
  // 기본은 한 줄에 6장이고, 높이가 모자랄 때만 카드를 더 줄인다.
  let tileWidth = Math.floor((inner - gap * 5) / 6);
  let columns = 6;
  for (; tileWidth > 16; tileWidth--) {
    columns = Math.max(1, Math.floor((inner + gap) / (tileWidth + gap)));
    if (heightFor(tileWidth, columns) <= available) break;
  }
  const tileHeight = tileWidth * CARD_RATIO;
  const zoneRows = rowsFor(columns);
  // 영역명·매수 표시가 마지막 줄 카드와 겹치는지. 겹치면 표시 뒤에 배경 상자를 깐다.
  const counterSize = { width: 48, height: 32 };
  const overlaps = (zone: DeckZone, rows: number) => {
    const count = tiles[zone].length;
    const last = count - (rows - 1) * columns;
    if (count === 0) return false;
    const lastRight = last * (tileWidth + gap) - gap;
    const content = rows * tileHeight + (rows - 1) * gap;
    const room = (zoneHeights[zone] ?? 0) - zonePad * 2 - 2 - content;
    return lastRight > inner - counterSize.width && room < counterSize.height;
  };

  // 드래그 앤 드롭. 카드를 잠깐 누르고 있으면 들어 올려지고, 다른 영역에 놓으면 옮겨진다.
  const zoneRefs = {
    list: useRef<View>(null),
    hand: useRef<View>(null),
    side: useRef<View>(null),
  };
  const gridRefs = {
    list: useRef<View>(null),
    hand: useRef<View>(null),
    side: useRef<View>(null),
  };
  const state = useRef({
    zones: {} as Partial<Record<DeckZone, Rect>>,
    grids: {} as Partial<Record<DeckZone, Rect>>,
    root: { x: 0, y: 0 },
    start: { x: 0, y: 0 },
    /** 누르고 있는 카드. 움직이면 바로 드래그가 된다. */
    pressed: null as Drag | null,
    drag: null as Drag | null,
  }).current;
  const latest = useRef({ tiles, deck, columns, tileWidth, tileHeight });
  latest.current = { tiles, deck, columns, tileWidth, tileHeight };
  const measure = (ref: React.RefObject<View | null>) =>
    new Promise<Rect>((resolve) =>
      ref.current
        ? ref.current.measure((_x, _y, w, h, pageX, pageY) =>
            resolve({ x: pageX, y: pageY, width: w, height: h }),
          )
        : resolve({ x: 0, y: 0, width: 0, height: 0 }),
    );
  const measureAll = async () => {
    const [root, ...rects] = await Promise.all([
      measure(pageRef),
      ...DECK_ZONES.flatMap((zone) => [
        measure(zoneRefs[zone]),
        measure(gridRefs[zone]),
      ]),
    ]);
    DECK_ZONES.forEach((zone, i) => {
      state.zones[zone] = rects[i * 2];
      state.grids[zone] = rects[i * 2 + 1];
    });
    state.root = { x: root!.x, y: root!.y };
  };
  const inside = (r: Rect | undefined, x: number, y: number) =>
    !!r && x >= r.x && x <= r.x + r.width && y >= r.y && y <= r.y + r.height;
  const zoneAt = (x: number, y: number) =>
    DECK_ZONES.find((zone) => inside(state.zones[zone], x, y)) || null;
  const moveGhost = (x: number, y: number) => {
    const { tileWidth, tileHeight } = latest.current;
    ghost.setValue({
      x: x - state.root.x - tileWidth / 2,
      y: y - state.root.y - tileHeight * 0.75,
    });
  };
  const endDrag = (x?: number, y?: number) => {
    const current = state.drag;
    state.drag = null;
    state.pressed = null;
    setDrag(null);
    setHover(null);
    onDragging(false);
    if (!current || x === undefined || y === undefined) return;
    const to = zoneAt(x, y);
    if (!to || to === current.zone || !current.tile.card) return;
    tapFeedback("selection");
    onChangeCards(
      moveCopy(latest.current.deck.cards, current.tile.card, current.zone, to),
    );
  };
  // 카드 위에서 시작한 터치는 항상 그 카드의 드래그 앤 드롭으로 다룬다.
  // 카드가 터치 응답자가 되고 응답자 승인에서 true를 돌려주면, 바깥 가로 스와이프(네이티브
  // 스크롤)가 이 터치를 가로채지 못한다. 카드가 없는 빈 곳에서 시작하면 스와이프로 화면이 넘어간다.
  const DRAG_SLOP = 6;
  const tileResponder = (tile: ZoneTile, zone: DeckZone) => ({
    onStartShouldSetResponder: () => true,
    onResponderTerminationRequest: () => false,
    onResponderGrant: (e: GestureResponderEvent) => {
      const { pageX, pageY } = e.nativeEvent;
      state.start = { x: pageX, y: pageY };
      state.pressed = { tile, zone };
      state.drag = null;
      measureAll();
      return true;
    },
    onResponderMove: (e: GestureResponderEvent) => {
      const { pageX, pageY } = e.nativeEvent;
      if (!state.drag) {
        const pressed = state.pressed;
        if (
          !pressed?.tile.card ||
          !isMovable(pressed.tile.card) ||
          (Math.abs(pageX - state.start.x) < DRAG_SLOP &&
            Math.abs(pageY - state.start.y) < DRAG_SLOP)
        )
          return;
        state.drag = pressed;
        onDragging(true);
        tapFeedback("light");
        setSelected(null);
        setDrag(pressed);
      }
      moveGhost(pageX, pageY);
      const over = zoneAt(pageX, pageY);
      setHover((previous) => (previous === over ? previous : over));
    },
    onResponderRelease: (e: GestureResponderEvent) => {
      if (state.drag) {
        endDrag(e.nativeEvent.pageX, e.nativeEvent.pageY);
        return;
      }
      // 움직이지 않고 뗐으면 카드 선택(동작 바)을 켜고 끈다.
      const pressed = state.pressed;
      state.pressed = null;
      if (!pressed) return;
      setSelected((previous) =>
        previous?.tile.key === pressed.tile.key &&
        previous.zone === pressed.zone
          ? null
          : pressed,
      );
    },
    onResponderTerminate: () => endDrag(),
  });

  const entryOf = (id: number) => deck.cards.find((e) => e.card_id === id);
  const selectedCard = selected?.tile.card;
  const selectedStillThere =
    !!selected &&
    tiles[selected.zone].some((tile) => tile.card_id === selected.tile.card_id);

  return (
    <View ref={pageRef} style={{ flex: 1, padding: pad }}>
      <View style={{ flex: 1, gap: zoneGap }}>
        {DECK_ZONES.map((zone, zoneIndex) => {
          const list = tiles[zone];
          const counter = counters[zone];
          const active = !!drag && hover === zone && drag.zone !== zone;
          const rows = zoneRows[zoneIndex]!;
          return (
            <View
              key={zone}
              ref={zoneRefs[zone]}
              onLayout={(e) => {
                const value = e.nativeEvent.layout.height;
                setZoneHeights((previous) =>
                  previous[zone] === value
                    ? previous
                    : { ...previous, [zone]: value },
                );
              }}
              style={[
                editorStyles.zone,
                {
                  padding: zonePad,
                  minHeight:
                    rows * tileHeight + (rows - 1) * gap + zonePad * 2 + 2,
                },
                // 남는 높이는 리스트 영역이 차지한다.
                zone === "list" && { flexGrow: 1 },
                active && editorStyles.zoneActive,
              ]}
            >
              <View ref={gridRefs[zone]} style={[editorStyles.grid, { gap }]}>
                {list.length === 0 && (
                  <View
                    style={[
                      editorStyles.emptyZone,
                      { height: tileHeight, width: inner - tileWidth - gap },
                    ]}
                  >
                    <Text style={styles.muted} numberOfLines={2}>
                      {t(
                        zone === "list"
                          ? "카드 검색에서 넣어 주세요."
                          : "비어 있음",
                      )}
                    </Text>
                  </View>
                )}
                {list.map((tile) => {
                  const lifted =
                    drag?.tile.key === tile.key && drag.zone === zone;
                  const picked =
                    selected?.tile.key === tile.key && selected.zone === zone;
                  return (
                    <View
                      key={tile.key}
                      {...tileResponder(tile, zone)}
                      accessible
                      accessibilityRole="button"
                      accessibilityLabel={
                        (tile.card ? localized(tile.card, language) : "") +
                        ", " +
                        t(ZONE_LABEL[zone])
                      }
                      onAccessibilityTap={() => setSelected({ tile, zone })}
                      style={[
                        {
                          width: tileWidth,
                          height: tileHeight,
                          borderRadius: 6,
                        },
                        lifted && { opacity: 0.3 },
                        picked && editorStyles.picked,
                      ]}
                    >
                      <CachedImage
                        url={
                          tile.card ? cardImageFor(tile.card, tileWidth) : ""
                        }
                        fill
                        height={tileHeight}
                      />
                      {!!tile.card && !isMovable(tile.card) && (
                        <View style={editorStyles.lock}>
                          <Icon
                            name="lock-closed"
                            size={10}
                            color={colors.text}
                          />
                        </View>
                      )}
                    </View>
                  );
                })}
              </View>
              <View
                pointerEvents="none"
                style={[
                  editorStyles.counter,
                  { right: zonePad, bottom: zonePad },
                  overlaps(zone, rows) && editorStyles.counterBox,
                ]}
              >
                <Text style={editorStyles.counterName}>
                  {t(ZONE_LABEL[zone])}
                </Text>
                <Text
                  style={[
                    editorStyles.counterValue,
                    { color: counter.ok ? colors.accent : colors.danger },
                  ]}
                >
                  {counter.value}
                </Text>
              </View>
            </View>
          );
        })}
      </View>

      {selectedStillThere && selectedCard && (
        <View style={editorStyles.actionBar}>
          <View style={editorStyles.actionHead}>
            <Text style={editorStyles.actionName} numberOfLines={1}>
              {localized(selectedCard, language)}
            </Text>
            <Text style={styles.muted}>
              {t(ZONE_LABEL[selected!.zone]) +
                " · ×" +
                (entryOf(selectedCard.id)?.count || 0)}
            </Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("닫기")}
              onPress={() => setSelected(null)}
              hitSlop={10}
            >
              <Icon name="close" size={20} color={colors.muted} />
            </Pressable>
          </View>
          <View style={editorStyles.actionRow}>
            {isMovable(selectedCard) &&
              DECK_ZONES.filter((z) => z !== selected!.zone).map((zone) => (
                <Button
                  key={zone}
                  size="sm"
                  variant="secondary"
                  icon="swap-horizontal"
                  label={ZONE_LABEL[zone] + "로"}
                  onPress={() => {
                    tapFeedback("selection");
                    onChangeCards(
                      moveCopy(deck.cards, selectedCard, selected!.zone, zone),
                    );
                    setSelected(null);
                  }}
                />
              ))}
            <Button
              size="sm"
              variant="danger"
              icon="remove-circle-outline"
              label="1장 빼기"
              onPress={() => {
                tapFeedback("selection");
                onChangeCards(
                  removeCopy(deck.cards, selectedCard.id, selected!.zone),
                );
              }}
            />
            <Button
              size="sm"
              variant="ghost"
              icon="expand-outline"
              label="카드 정보"
              onPress={() =>
                router.push({
                  pathname: "/card/[id]",
                  params: { id: selectedCard.id },
                })
              }
            />
          </View>
        </View>
      )}

      {drag?.tile.card && (
        <Animated.View
          pointerEvents="none"
          style={[
            editorStyles.ghost,
            {
              width: tileWidth * 1.25,
              transform: [
                { translateX: ghost.x },
                { translateY: ghost.y },
                { rotate: "-4deg" },
              ],
            },
          ]}
        >
          <CachedImage
            url={cardImageFor(drag.tile.card, tileWidth * 1.25)}
            fill
            height={tileWidth * 1.25 * CARD_RATIO}
          />
        </Animated.View>
      )}
    </View>
  );
}

function countUltimates(tiles: ZoneTile[]) {
  return tiles.filter((tile) => tile.card?.ultimate).length;
}

// ── 덱 정보 ──────────────────────────────────────────────────

function InfoPage({
  deck,
  catalog,
  width,
  versions,
  issues,
  onChange,
  onImport,
  onError,
}: {
  deck: Deck;
  catalog: Catalog;
  width: number;
  versions: RegulationVersion[];
  issues: ReturnType<typeof deckIssues>;
  onChange: (patch: Partial<Deck>) => void;
  onImport: (deck: Deck) => void;
  onError: (message: string) => void;
}) {
  const { language, t } = useApp();
  const [importText, setImportText] = useState("");
  const character = catalog.characters.find((c) => c.id === deck.character_id);
  const content = Math.min(width, 760);
  const keeps = (cardId: number, characterId: number) => {
    const card = catalog.cards.find((c) => c.id === cardId);
    return !!card && usableBy(card, characterId);
  };
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{
        width: content,
        alignSelf: "center",
        padding: space.lg,
        paddingBottom: space.xxl,
      }}
    >
      {!deck.character_id && (
        <View style={editorStyles.callout}>
          <Icon name="person-add-outline" size={20} color={colors.accent} />
          <Text style={[styles.text, { flex: 1 }]}>
            {t("먼저 덱의 캐릭터를 선택해주세요.")}
          </Text>
        </View>
      )}
      <EditorSection title="캐릭터">
        <CharacterGrid
          characters={catalog.characters}
          value={deck.character_id ? String(deck.character_id) : ""}
          width={content - space.lg * 4}
          size={48}
          onChange={(value) => {
            const id = Number(value);
            const next = catalog.characters.find((c) => c.id === id);
            if (!next || id === deck.character_id) return;
            onChange({
              character_id: id,
              // 캐릭터를 바꾸면 새 캐릭터가 쓸 수 없는 카드만 정리하고
              // 세츠메이(중립) 카드는 남긴다.
              cards: deck.cards.filter((e) => keeps(e.card_id, id)),
              reserve_cards: (deck.reserve_cards || []).filter((e) =>
                keeps(e.card_id, id),
              ),
              trait_card_id:
                next.traits?.length === 1 ? next.traits[0]!.id : null,
            });
          }}
        />
        {!!character?.traits?.length && (
          <>
            <FieldLabel text="특성" style={{ marginTop: space.lg }} />
            <ChipRow>
              {character.traits.map((trait) => (
                <Chip
                  key={trait.id}
                  label={localized(trait, language) || trait.name}
                  selected={deck.trait_card_id === trait.id}
                  onPress={() => onChange({ trait_card_id: trait.id })}
                />
              ))}
            </ChipRow>
          </>
        )}
      </EditorSection>

      <EditorSection title="기본 정보">
        <FieldLabel text="덱 이름" />
        <Input
          accessibilityLabel={t("덱 이름")}
          value={deck.name}
          onChangeText={(name) => onChange({ name })}
        />
        <FieldLabel text="공개 범위" />
        <Segmented
          value={deck.visibility}
          onChange={(v) => onChange({ visibility: v as Deck["visibility"] })}
          values={[
            { key: "private", label: "비공개", icon: "lock-closed-outline" },
            { key: "unlisted", label: "일부 공개", icon: "link-outline" },
            { key: "public", label: "공개", icon: "globe-outline" },
          ]}
        />
        <View style={editorStyles.labelRow}>
          <FieldLabel text="적용 규정" />
          <Button
            label="규정 작성·복사"
            icon="document-text-outline"
            variant="ghost"
            size="sm"
            onPress={() => router.push("/regulations")}
          />
        </View>
        <ChipRow>
          <Chip
            label="기본 규정"
            selected={!deck.regulation_version_id}
            onPress={() =>
              onChange({
                regulation_version_id: null,
                regulation_rules: undefined,
              })
            }
          />
          {versions.map((v) => (
            <Chip
              key={v.id}
              label={v.name + " / " + v.version}
              selected={deck.regulation_version_id === v.id}
              onPress={() =>
                onChange({
                  regulation_version_id: v.id,
                  regulation_rules: v.rules,
                })
              }
            />
          ))}
        </ChipRow>
        <FieldLabel text="덱 설명" />
        <Input
          accessibilityLabel={t("덱 설명")}
          placeholder={t("덱 설명")}
          multiline
          textAlignVertical="top"
          style={{ minHeight: 96 }}
          value={deck.description}
          onChangeText={(description) => onChange({ description })}
        />
      </EditorSection>

      <EditorSection title="편성 확인">
        {issues.length === 0 ? (
          <View style={editorStyles.issue}>
            <Icon name="checkmark-circle" size={18} color={colors.success} />
            <Text style={[styles.text, { flex: 1 }]}>
              {t("문제가 없습니다.")}
            </Text>
          </View>
        ) : (
          issues.map((issue, n) => (
            <View key={n} style={editorStyles.issue}>
              <Icon
                name={issue.severity === "error" ? "alert-circle" : "warning"}
                size={18}
                color={
                  issue.severity === "error" ? colors.danger : colors.accent
                }
              />
              <Text style={[styles.text, { flex: 1, fontSize: 14 }]}>
                {t(issue.message)}
              </Text>
            </View>
          ))
        )}
        {(deck.reserve_cards || []).length > 0 && (
          <Text style={[styles.muted, { marginTop: space.sm }]}>
            {t("교체 덱") +
              " " +
              (deck.reserve_cards || []).reduce((n, e) => n + e.count, 0) +
              t("장") +
              " · " +
              t("교체 덱은 웹에서 편집할 수 있습니다.")}
          </Text>
        )}
      </EditorSection>

      <EditorSection title="덱 코드로 가져오기">
        <Input
          accessibilityLabel={t("가져올 덱 코드")}
          placeholder={t("가져올 덱 코드 붙여넣기")}
          value={importText}
          onChangeText={setImportText}
        />
        <Button
          label="가져오기"
          icon="download-outline"
          disabled={!importText}
          onPress={() => {
            try {
              onImport(
                importDeckCode(importText, catalog, Crypto.randomUUID()),
              );
              setImportText("");
            } catch (e) {
              onError(userMessage(e));
            }
          }}
        />
      </EditorSection>
    </ScrollView>
  );
}

function EditorSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <View style={{ marginBottom: space.xl }}>
      <Text style={[editorStyles.sectionTitle, { marginLeft: space.xs }]}>
        {t(title)}
      </Text>
      <View style={editorStyles.section}>{children}</View>
    </View>
  );
}

function FieldLabel({ text, style }: { text: string; style?: object }) {
  const { t } = useApp();
  return <Text style={[editorStyles.fieldLabel, style]}>{t(text)}</Text>;
}

function ChipRow({ children }: { children: React.ReactNode }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{ gap: space.sm }}
      style={{ flexGrow: 0, marginBottom: space.md }}
    >
      {children}
    </ScrollView>
  );
}

const editorStyles = StyleSheet.create({
  save: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: space.md,
    paddingVertical: 6,
    marginRight: space.xs,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
  },
  saveBlocked: { backgroundColor: colors.surface2 },
  saveText: { color: colors.onAccent, fontSize: 14, fontWeight: "700" },
  tabs: {
    flexDirection: "row",
    backgroundColor: colors.panel,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  tab: { flex: 1, minHeight: 58, alignItems: "center" },
  tabIndicator: {
    alignSelf: "stretch",
    height: 3,
    backgroundColor: "transparent",
  },
  tabInner: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 2,
  },
  tabLabel: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  tabBadge: {
    position: "absolute",
    top: 2,
    right: -18,
    minWidth: 20,
    paddingHorizontal: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: "center",
  },
  tabBadgeText: { color: colors.onAccent, fontSize: 11, fontWeight: "800" },
  tileName: {
    color: colors.text,
    fontSize: 11,
    fontWeight: "600",
    marginTop: 3,
  },
  countBadge: {
    position: "absolute",
    right: 3,
    bottom: 3,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
  },
  countBadgeText: { color: colors.onAccent, fontSize: 11, fontWeight: "800" },
  headerRight: { flexDirection: "row", alignItems: "center", gap: 6 },
  meter: {
    minWidth: 44,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radius.sm,
    borderWidth: 1,
    alignItems: "center",
  },
  meterText: { fontSize: 13, fontWeight: "800" },
  guide: {
    position: "absolute",
    top: space.xs,
    right: space.md,
    maxWidth: 260,
    padding: space.md,
    gap: 4,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    elevation: 8,
  },
  guideTitle: { color: colors.text, fontSize: 14, fontWeight: "700" },
  guideText: { color: colors.muted, fontSize: 13 },
  counter: { position: "absolute", alignItems: "flex-end" },
  counterBox: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: "rgba(17, 17, 17, 0.88)",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  counterName: { color: colors.muted, fontSize: 10, fontWeight: "700" },
  counterValue: { fontSize: 13, fontWeight: "800" },
  zone: {
    padding: space.sm,
    borderRadius: radius.md,
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: colors.line,
  },
  zoneActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentSoft,
  },
  zoneHead: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    height: 22,
    marginBottom: space.sm,
  },
  zoneTitle: { color: colors.text, fontSize: 14, fontWeight: "700" },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  emptyZone: {
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 6,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.line,
  },
  picked: { borderWidth: 2, borderColor: colors.accent },
  lock: {
    position: "absolute",
    top: 2,
    right: 2,
    padding: 2,
    borderRadius: radius.pill,
    backgroundColor: "rgba(0,0,0,0.6)",
  },
  ghost: {
    position: "absolute",
    left: 0,
    top: 0,
    shadowColor: "#000",
    shadowOpacity: 0.5,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
    elevation: 12,
  },
  actionBar: {
    position: "absolute",
    left: space.md,
    right: space.md,
    bottom: space.md,
    padding: space.md,
    gap: space.sm,
    borderRadius: radius.lg,
    backgroundColor: colors.surface2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    elevation: 8,
  },
  actionHead: { flexDirection: "row", alignItems: "center", gap: space.sm },
  actionName: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "700",
    flexShrink: 1,
  },
  actionRow: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  callout: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    padding: space.md,
    marginBottom: space.lg,
    borderRadius: radius.md,
    backgroundColor: colors.accentSoft,
    borderWidth: 1,
    borderColor: colors.accent,
  },
  sectionTitle: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    marginBottom: space.sm,
  },
  section: {
    padding: space.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  issue: {
    flexDirection: "row",
    gap: space.sm,
    alignItems: "flex-start",
    paddingVertical: 4,
  },
});
