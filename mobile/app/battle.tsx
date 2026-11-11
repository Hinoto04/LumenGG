import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Share, StyleSheet, Text, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { ApiError } from "../src/api";
import {
  chooseRoomDeck,
  createBattle,
  createRoom,
  joinRoom,
  joinedRoom,
  lastBattle,
  leaveRoom,
  quickMatch,
  rememberBattle,
  rememberRoom,
  roomState,
  searchPublicDecks,
  setRoomReady,
  type BattleMode,
  type LastBattle,
  type PublicDeck,
} from "../src/battle";
import {
  mySeat,
  normalizeRoomCode,
  roomOptionsText,
  roomOutcome,
  seatDeckText,
  type JoinedRoom,
  type RoomKind,
  type RoomResponse,
  type RoomSeat,
  type RoomView,
} from "../src/battle-room";
import { useApp } from "../src/provider";
import {
  Badge,
  Button,
  Choices,
  Icon,
  Input,
  Notice,
  SearchInput,
  Segmented,
  colors,
  radius,
  space,
  styles,
} from "../src/ui";
import { BottomSheet, CharacterAvatar, PlayerSlot, Versus } from "../src/character-picker";
import type { Character } from "../src/types";

interface DeckOption {
  id: number;
  name: string;
  character_id: number;
  note?: string;
}

type Tab = "ai" | RoomKind;

const TIMERS = [0, 10, 15, 30, 45, 60, 90, 120];
const POLL_MS = 1500;

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail;
    if (detail && typeof detail === "object" && "error" in detail) return String(detail.error);
    if (error.status === 401 || error.status === 403) return "덱을 볼 권한이 없습니다. 로그인 상태를 확인해 주세요.";
  }
  return error instanceof Error ? error.message : String(error);
}

function DeckRow({
  deck,
  selected,
  character,
  characterName,
  onPress,
}: {
  deck: DeckOption;
  selected: boolean;
  character?: Character;
  characterName: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      accessibilityLabel={`${characterName} · ${deck.name}`}
      onPress={onPress}
      style={({ pressed }) => [
        battleStyles.deckRow,
        selected && battleStyles.deckRowSelected,
        pressed && { opacity: 0.8 },
      ]}
    >
      <CharacterAvatar character={character} size={44} selected={selected} />
      <View style={{ flex: 1 }}>
        <Text style={battleStyles.deckName} numberOfLines={1}>
          {deck.name}
        </Text>
        <Text style={styles.muted} numberOfLines={1}>
          {characterName}
          {deck.note ? ` · ${deck.note}` : ""}
        </Text>
      </View>
      {selected && <Icon name="checkmark-circle" size={22} color={colors.accent} />}
    </Pressable>
  );
}

function TimerChoices({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <View>
      <Text style={[styles.muted, { marginBottom: 6 }]}>{label}</Text>
      <Choices
        values={TIMERS.map((seconds) => ({ key: String(seconds), label: seconds ? `${seconds}초` : "없음" }))}
        value={String(value)}
        onChange={(v) => onChange(Number(v))}
      />
    </View>
  );
}

/**
 * 참가 중인 방(퀵 매치 포함)을 1.5초마다 갱신하고, 대전이 시작되면 onStart로 내 좌석 주소를 넘긴다.
 * 참가 정보(코드·자리 토큰)는 기기에 저장해 화면을 떠났다 와도 이어진다.
 */
function useRoom(onStart: (url: string, room: RoomView) => void) {
  const [joined, setJoined] = useState<JoinedRoom | null>(null);
  const [room, setRoom] = useState<RoomView | null>(null);
  const [closed, setClosed] = useState(false);
  const [error, setError] = useState("");
  // 나가기·시작 뒤에 도착한 이전 응답은 버린다.
  const generation = useRef(0);
  const startRef = useRef(onStart);
  startRef.current = onStart;

  useEffect(() => {
    joinedRoom().then((saved) => {
      if (saved) setJoined(saved);
    });
  }, []);

  const reset = useCallback(() => {
    generation.current += 1;
    setJoined(null);
    setRoom(null);
    void rememberRoom(null);
  }, []);

  const apply = useCallback(
    (data: RoomResponse, kind: RoomKind, from: number) => {
      if (from !== generation.current) return;
      const outcome = roomOutcome(data.room);
      if (outcome.kind === "closed") {
        reset();
        setClosed(true);
        return;
      }
      if (outcome.kind === "play") {
        reset();
        startRef.current(outcome.url, data.room);
        return;
      }
      const next: JoinedRoom = { code: data.room.code, token: data.token, kind };
      setClosed(false);
      setJoined((current) => (current?.code === next.code && current.token === next.token ? current : next));
      setRoom(data.room);
      void rememberRoom(next);
    },
    [reset],
  );

  useEffect(() => {
    if (!joined) return;
    const from = generation.current;
    let alive = true;
    const tick = async () => {
      try {
        const data = await roomState(joined);
        if (alive) apply(data, joined.kind, from);
      } catch (exception) {
        if (!alive) return;
        // 방을 찾을 수 없으면(만료·정리됨) 기다림을 끝낸다.
        if (exception instanceof ApiError && exception.status === 400) {
          reset();
          setClosed(true);
        } else setError(errorText(exception));
      }
    };
    void tick();
    const timer = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [joined, apply, reset]);

  /** 방을 만들거나 참가하는 요청(퀵 매치 포함) */
  const enter = async (kind: RoomKind, call: () => Promise<RoomResponse>) => {
    setError("");
    setClosed(false);
    const from = generation.current;
    try {
      apply(await call(), kind, from);
    } catch (exception) {
      setError(errorText(exception));
    }
  };

  /** 참가 중인 방에 대한 요청(덱 · 준비) */
  const act = async (call: (room: JoinedRoom) => Promise<RoomResponse>) => {
    if (!joined) return;
    setError("");
    const from = generation.current;
    try {
      apply(await call(joined), joined.kind, from);
    } catch (exception) {
      setError(errorText(exception));
    }
  };

  const leave = async () => {
    const current = joined;
    reset();
    setError("");
    if (!current) return;
    try {
      await leaveRoom(current);
    } catch {
      /* 이미 닫힌 방이어도 화면에서는 나간다 */
    }
  };

  return { joined, room, closed, error, enter, act, leave };
}

function SeatCard({ seat, label, character }: { seat: RoomSeat; label: string; character?: Character }) {
  const { t } = useApp();
  return (
    <View style={[battleStyles.seat, seat.me && { borderColor: colors.accent }]}>
      <Text style={battleStyles.seatLabel}>{t(label)}</Text>
      <CharacterAvatar character={seat.present ? character : null} size={56} selected={!!seat.me} dim={!seat.present} />
      {seat.present && (
        <Text style={[styles.text, { fontWeight: "700" }]} numberOfLines={1}>
          {seat.name || t("플레이어")}
        </Text>
      )}
      <Text style={[styles.muted, { textAlign: "center" }]} numberOfLines={2}>
        {t(seatDeckText(seat))}
      </Text>
      {seat.present && <Badge label={seat.ready ? "준비 완료" : "준비 전"} tone={seat.ready ? "success" : "neutral"} />}
    </View>
  );
}

/**
 * 대전: AI와 대전 · 방 · 퀵 매치. 웹 로비(/battlelog/play/)와 같은 방식이다.
 * 사람끼리 대전은 각자 자기 덱만 고른다(서버 battlelog/play_rooms.py). 덱은 서버에 저장된(동기화된) 덱만 쓸 수 있다.
 * 대전 화면은 WebView(/play)로 연다.
 */
export default function Battle() {
  const { decks, catalog, language, user, t } = useApp();
  const [tab, setTab] = useState<Tab>("ai");
  const [mine, setMine] = useState<number | null>(null);
  const [rivalSource, setRivalSource] = useState<"same" | "mine" | "public">("same");
  const [rival, setRival] = useState<number | null>(null);
  const [aiReadyTimer, setAiReadyTimer] = useState(10);
  const [aiEffectTimer, setAiEffectTimer] = useState(30);
  const [mode, setMode] = useState<BattleMode>("automatic");
  const [readyTimer, setReadyTimer] = useState(10);
  const [effectTimer, setEffectTimer] = useState(30);
  const [code, setCode] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PublicDeck[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [resume, setResume] = useState<LastBattle | null>(null);
  const [waitingSince, setWaitingSince] = useState(() => Date.now());
  const [, setClock] = useState(0);

  useFocusEffect(
    React.useCallback(() => {
      lastBattle().then(setResume);
    }, []),
  );

  const characterName = (id: number) =>
    catalog?.characters.find((c) => c.id === id)?.localized?.[language]?.name ?? `#${id}`;
  const characterOf = (id?: number | null) => catalog?.characters.find((c) => c.id === id);
  // 방 좌석에는 캐릭터 이름만 오므로 이름으로 얼굴을 찾는다.
  const characterNamed = (name?: string | null) =>
    name
      ? catalog?.characters.find((c) =>
          Object.values(c.localized || {}).some((l: any) => l?.name === name),
        )
      : undefined;
  const [picker, setPicker] = useState<{
    kind: "mine" | "rival";
    title: string;
    selected: number | null | undefined;
    onPick: (id: number) => void;
  } | null>(null);
  const [rivalInfo, setRivalInfo] = useState<DeckOption | null>(null);

  // 서버 id가 있는(동기화된) 덱만 대전에 쓸 수 있다.
  const synced: DeckOption[] = useMemo(
    () =>
      decks
        .filter((deck) => deck.id && !deck.deleted)
        .map((deck) => ({ id: deck.id!, name: deck.name, character_id: deck.character_id })),
    [decks],
  );
  const unsynced = decks.filter((deck) => !deck.id && !deck.deleted).length;

  const openSeat = async (url: string, label: string) => {
    await rememberBattle(url, label);
    setResume(await lastBattle());
    router.push({ pathname: "/play", params: { url } });
  };

  const lobby = useRoom((url, started) => {
    const kind = started.kind === "quick" ? "퀵 매치" : started.options.mode === "manual" ? "수동 대전" : "친구 대전";
    void openSeat(url, `${mySeat(started).deck?.character ?? ""} · ${kind}`);
  });
  const { joined, room } = lobby;

  // 저장된 방으로 이어질 때 그 탭을 연다.
  useEffect(() => {
    if (joined) setTab(joined.kind);
  }, [joined?.kind]); // eslint-disable-line react-hooks/exhaustive-deps

  const quickWaiting = joined?.kind === "quick" && room?.status === "waiting";
  useEffect(() => {
    if (!quickWaiting) return;
    const timer = setInterval(() => setClock((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [quickWaiting]);

  useEffect(() => {
    if (tab !== "ai" || rivalSource !== "public") return;
    const text = query.trim();
    if (text.length < 2) {
      setResults([]);
      return;
    }
    const timer = setTimeout(() => {
      searchPublicDecks(text)
        .then(setResults)
        .catch(() => setResults([]));
    }, 300);
    return () => clearTimeout(timer);
  }, [query, rivalSource, tab]);

  const rivalDeck = rivalSource === "same" ? mine : rival;

  const startAi = async () => {
    if (!mine || !rivalDeck) return;
    setBusy(true);
    setError("");
    try {
      const session = await createBattle({
        p1_deck: mine,
        p2_deck: rivalDeck,
        opponent: "ai",
        mode: "automatic",
        ready_timeout_seconds: aiReadyTimer,
        effect_timeout_seconds: aiEffectTimer,
      });
      await openSeat(session.urls.p1, `${characterName(synced.find((d) => d.id === mine)?.character_id ?? 0)} · AI 대전`);
    } catch (exception) {
      setError(errorText(exception));
    } finally {
      setBusy(false);
    }
  };

  const run = async (task: () => Promise<void>) => {
    setBusy(true);
    try {
      await task();
    } finally {
      setBusy(false);
    }
  };

  const myDecks = (selected: number | null | undefined, onPress: (id: number) => void) => (
    <>
      {!user && <Notice text={t("로그인하고 덱을 동기화하면 내 덱으로 대전할 수 있습니다.")} />}
      {user && !synced.length && <Notice text={t("서버에 저장된 덱이 없습니다. 덱 화면에서 덱을 만들어 주세요.")} />}
      {synced.map((deck) => (
        <DeckRow
          key={deck.id}
          deck={deck}
          selected={selected === deck.id}
          character={characterOf(deck.character_id)}
          characterName={characterName(deck.character_id)}
          onPress={() => onPress(deck.id)}
        />
      ))}
      {unsynced > 0 && <Text style={styles.muted}>{t(`동기화되지 않은 덱 ${unsynced}개는 대전에 쓸 수 없습니다.`)}</Text>}
    </>
  );

  const deckSlot = (
    label: string,
    selected: number | null | undefined,
    onPick: (id: number) => void,
    accent?: string,
  ) => {
    const deck = synced.find((d) => d.id === selected);
    return (
      <PlayerSlot
        label={label}
        accent={accent}
        character={characterOf(deck?.character_id)}
        title={deck ? deck.name : t("덱 선택")}
        subtitle={deck ? characterName(deck.character_id) : t("눌러서 덱을 고릅니다.")}
        onPress={() => setPicker({ kind: "mine", title: "내 덱", selected, onPick })}
      />
    );
  };
  const rivalOption =
    rivalSource === "same" ? synced.find((d) => d.id === mine) : rivalSource === "mine" ? synced.find((d) => d.id === rival) : rivalInfo;

  const aiTab = (
    <>
      {!user && <Notice text={t("로그인하고 덱을 동기화하면 내 덱으로 대전할 수 있습니다.")} />}
      {user && !synced.length && <Notice text={t("서버에 저장된 덱이 없습니다. 덱 화면에서 덱을 만들어 주세요.")} />}
      <View style={battleStyles.versus}>
        {deckSlot("나", mine, setMine)}
        <Versus />
        <PlayerSlot
          label="AI"
          accent="#5fc8c0"
          character={characterOf(rivalOption?.character_id)}
          title={rivalOption ? rivalOption.name : t("덱 선택")}
          subtitle={
            rivalSource === "same"
              ? t("같은 덱")
              : rivalOption
                ? characterName(rivalOption.character_id)
                : t("눌러서 덱을 고릅니다.")
          }
          onPress={() => setPicker({ kind: "rival", title: "AI가 쓸 덱", selected: rival, onPick: setRival })}
        />
      </View>
      <View style={styles.panel}>
        <TimerChoices label={t("레디 제한 시간")} value={aiReadyTimer} onChange={setAiReadyTimer} />
        <TimerChoices label={t("효과 선택 제한 시간")} value={aiEffectTimer} onChange={setAiEffectTimer} />
      </View>
      {error ? <Notice text={error} /> : null}
      <Button
        label={busy ? "만드는 중…" : "대전 시작"}
        icon="flash"
        variant="primary"
        block
        loading={busy}
        disabled={!mine || !rivalDeck}
        onPress={startAi}
      />
    </>
  );

  const roomLobby = (current: RoomView) => {
    const me = mySeat(current);
    return (
      <>
        <View style={styles.panel}>
          <Text style={styles.muted}>{t("방 코드")}</Text>
          <Text selectable style={[styles.title, { fontSize: 30, letterSpacing: 4 }]}>
            {current.code}
          </Text>
          <Text style={[styles.muted, { marginBottom: 10 }]}>{t(roomOptionsText(current.options))}</Text>
          {current.invite_url ? (
            <Button
              label="초대 보내기"
              onPress={() =>
                Share.share({ message: `${t("루멘콘덴서 대전 방 코드")}: ${current.code}\n${current.invite_url}` })
              }
            />
          ) : null}
        </View>
        <View style={battleStyles.versus}>
          <SeatCard
            seat={current.seats.host}
            label="방장 (P1)"
            character={characterNamed(current.seats.host.deck?.character)}
          />
          <Versus />
          <SeatCard
            seat={current.seats.guest}
            label="참가자 (P2)"
            character={characterNamed(current.seats.guest.deck?.character)}
          />
        </View>
        <View style={{ flexDirection: "row", marginBottom: space.md }}>
          {deckSlot("내 덱", me.deck?.id, (id) => {
            setMine(id);
            void lobby.act((target) => chooseRoomDeck(target, id));
          })}
        </View>
        {lobby.error || current.error ? <Notice text={lobby.error || current.error} /> : null}
        <View style={styles.row}>
          <Button label={current.seat === "host" ? "방 닫기" : "나가기"} danger onPress={() => void lobby.leave()} />
          <Button
            label={me.ready ? "준비 취소" : "준비 완료"}
            icon={me.ready ? "close-circle-outline" : "checkmark-circle-outline"}
            variant={me.ready ? "secondary" : "primary"}
            style={{ flex: 1 }}
            disabled={!me.deck}
            onPress={() => void lobby.act((target) => setRoomReady(target, !me.ready))}
          />
        </View>
        <Text style={[styles.muted, { marginTop: 8 }]}>{t("두 플레이어가 모두 덱을 고르고 준비하면 대전이 시작됩니다.")}</Text>
      </>
    );
  };

  const roomTab =
    joined?.kind === "room" && room ? (
      roomLobby(room)
    ) : (
      <>
        {lobby.closed && <Notice text={t("방이 닫혔습니다.")} />}
        <View style={{ flexDirection: "row" }}>{deckSlot("내 덱", mine, setMine)}</View>
        <Text style={[styles.muted, { marginVertical: space.sm }]}>
          {t("덱은 방에 들어간 뒤에 골라도 됩니다. 상대에게는 내 덱의 캐릭터만 보입니다.")}
        </Text>
        <View style={styles.panel}>
          <Text style={styles.title}>{t("방 만들기")}</Text>
          <Choices
            values={[
              { key: "automatic", label: t("자동 판정") },
              { key: "manual", label: t("수동(샌드박스)") },
            ]}
            value={mode}
            onChange={(v) => setMode(v as BattleMode)}
          />
          {mode === "automatic" ? (
            <>
              <TimerChoices label={t("레디 제한 시간")} value={readyTimer} onChange={setReadyTimer} />
              <TimerChoices label={t("효과 선택 제한 시간")} value={effectTimer} onChange={setEffectTimer} />
            </>
          ) : (
            <Text style={[styles.muted, { marginBottom: 10 }]}>
              {t("수동 대전은 규칙을 판정하지 않습니다. 카드 이동과 HP·FP를 직접 조작합니다.")}
            </Text>
          )}
          <Button
            label="방 만들기"
            icon="add-circle-outline"
            variant="primary"
            block
            disabled={busy || !!joined}
            onPress={() =>
              void run(() =>
                lobby.enter("room", () =>
                  createRoom({
                    deck_id: mine ?? undefined,
                    mode,
                    ready_timeout_seconds: readyTimer,
                    effect_timeout_seconds: effectTimer,
                  }),
                ),
              )
            }
          />
        </View>
        <View style={styles.panel}>
          <Text style={styles.title}>{t("코드로 참가")}</Text>
          <Input
            style={{ fontSize: 22, letterSpacing: 6, textAlign: "center" }}
            value={code}
            onChangeText={(text) => setCode(normalizeRoomCode(text))}
            autoCapitalize="characters"
            autoCorrect={false}
            placeholder={t("방 코드 6자리")}
          />
          <Button
            label="참가"
            disabled={busy || !!joined || code.length < 4}
            onPress={() => void run(() => lobby.enter("room", () => joinRoom(code, mine ?? undefined)))}
          />
        </View>
        {lobby.error ? <Notice text={lobby.error} /> : null}
      </>
    );

  const quickTab = quickWaiting ? (
    <View style={[styles.panel, { alignItems: "center" }]}>
      <ActivityIndicator color={colors.accent} style={{ marginBottom: 10 }} />
      <Text style={styles.text}>
        {t("상대를 찾는 중…")} {Math.max(0, Math.floor((Date.now() - waitingSince) / 1000))}
        {t("초")}
      </Text>
      <Text style={[styles.muted, { marginBottom: 10 }]}>
        {room?.seats.host.deck?.character} {t("덱 · 자동 판정 · 레디 10초 · 효과 선택 30초")}
      </Text>
      <Button label="매칭 취소" danger onPress={() => void lobby.leave()} />
      {lobby.error ? <Notice text={lobby.error} /> : null}
    </View>
  ) : (
    <>
      <View style={{ flexDirection: "row" }}>{deckSlot("내 덱", mine, setMine)}</View>
      <View style={[styles.panel, { marginTop: space.md }]}>
        <Text style={styles.muted}>
          {t("덱만 정하면 지금 퀵 매치를 기다리는 다른 플레이어와 자동 판정으로 대전합니다(레디 10초 · 효과 선택 30초).")}
        </Text>
      </View>
      {lobby.error ? <Notice text={lobby.error} /> : null}
      <Button
        label={busy ? "찾는 중…" : "퀵 매치 시작"}
        icon="search"
        variant="primary"
        block
        disabled={busy || !mine || !!joined}
        onPress={() =>
          void run(async () => {
            setWaitingSince(Date.now());
            await lobby.enter("quick", () => quickMatch(mine!));
          })
        }
      />
    </>
  );

  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ width: "100%", maxWidth: 760, alignSelf: "center", paddingBottom: 40 }}>
      {resume && (
        <View style={battleStyles.resume}>
          <Icon name="play-circle" size={28} color={colors.accent} />
          <View style={{ flex: 1 }}>
            <Text style={styles.muted}>{t("진행 중이던 대전")}</Text>
            <Text style={[styles.text, { fontWeight: "700" }]} numberOfLines={1}>
              {resume.label}
            </Text>
          </View>
          <Button
            label="이어하기"
            variant="primary"
            size="sm"
            onPress={() => router.push({ pathname: "/play", params: { url: resume.url } })}
          />
        </View>
      )}

      <Segmented
        values={[
          { key: "ai", label: "AI와 대전", icon: "hardware-chip-outline" },
          { key: "room", label: "방", icon: "people-outline" },
          { key: "quick", label: "퀵 매치", icon: "flash-outline" },
        ]}
        value={tab}
        onChange={(v) => {
          // 방이나 퀵 매치에 참가 중이면 다른 사람 대전 탭으로는 옮기지 않는다(먼저 나가기).
          if (joined && v !== joined.kind && v !== "ai") return;
          setTab(v as Tab);
          setError("");
        }}
      />

      {tab === "ai" && aiTab}
      {tab === "room" && roomTab}
      {tab === "quick" && quickTab}

      <BottomSheet
        visible={!!picker}
        title={picker?.title || ""}
        onClose={() => setPicker(null)}
        header={
          picker?.kind === "rival" ? (
            <>
              <Segmented
                values={[
                  { key: "same", label: "같은 덱" },
                  { key: "mine", label: "내 덱" },
                  { key: "public", label: "공개 덱" },
                ]}
                value={rivalSource}
                onChange={(v) => {
                  setRivalSource(v as typeof rivalSource);
                  setRival(null);
                  setRivalInfo(null);
                }}
              />
              {rivalSource === "public" && (
                <SearchInput value={query} onChangeText={setQuery} placeholder="덱 이름·작성자 (2글자 이상)" />
              )}
            </>
          ) : null
        }
      >
        {() =>
          picker?.kind === "rival" ? (
            rivalSource === "same" ? (
              <View style={{ gap: space.md, paddingBottom: space.md }}>
                <Text style={styles.muted}>{t("AI도 내가 고른 덱과 같은 덱을 씁니다.")}</Text>
                <Button label="확인" variant="primary" block onPress={() => setPicker(null)} />
              </View>
            ) : rivalSource === "mine" ? (
              myDecks(rival, (id) => {
                setRival(id);
                setPicker(null);
              })
            ) : (
              <>
                {query.trim().length >= 2 && !results.length && (
                  <Notice text={t("검색 결과가 없습니다.")} />
                )}
                {results.map((deck) => (
                  <DeckRow
                    key={deck.id}
                    deck={{ ...deck, note: deck.author?.username }}
                    selected={rival === deck.id}
                    character={characterOf(deck.character_id)}
                    characterName={characterName(deck.character_id)}
                    onPress={() => {
                      setRival(deck.id);
                      setRivalInfo({ id: deck.id, name: deck.name, character_id: deck.character_id });
                      setPicker(null);
                    }}
                  />
                ))}
              </>
            )
          ) : picker ? (
            myDecks(picker.selected, (id) => {
              picker.onPick(id);
              setPicker(null);
            })
          ) : null
        }
      </BottomSheet>
    </ScrollView>
  );
}

const battleStyles = StyleSheet.create({
  versus: {
    flexDirection: "row",
    alignItems: "stretch",
    gap: space.sm,
    marginBottom: space.md,
  },
  deckRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    padding: space.md,
    marginBottom: space.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
  },
  deckRowSelected: { borderColor: colors.accent, backgroundColor: colors.accentSoft },
  deckName: { color: colors.text, fontSize: 15, fontWeight: "700" },
  seat: {
    flex: 1,
    alignItems: "center",
    gap: 6,
    padding: space.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
  },
  seatLabel: { color: colors.muted, fontSize: 12, fontWeight: "700" },
  resume: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    padding: space.md,
    marginBottom: space.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.accent,
    backgroundColor: colors.accentSoft,
  },
});
