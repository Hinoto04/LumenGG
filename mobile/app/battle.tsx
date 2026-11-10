import React, { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, Share, Text, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { ApiError } from "../src/api";
import {
  createBattle,
  lastBattle,
  rememberBattle,
  searchPublicDecks,
  type BattleMode,
  type LastBattle,
  type Opponent,
  type PublicDeck,
} from "../src/battle";
import { useApp } from "../src/provider";
import { Button, Choices, Input, Notice, colors, styles } from "../src/ui";

interface DeckOption {
  id: number;
  name: string;
  character_id: number;
  note?: string;
}

const TIMERS = [0, 15, 30, 45, 60, 90, 120];

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
  characterName,
  onPress,
}: {
  deck: DeckOption;
  selected: boolean;
  characterName: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={{
        padding: 12,
        borderRadius: 10,
        borderWidth: 1,
        borderColor: selected ? colors.accent : colors.line,
        backgroundColor: selected ? "#2a2215" : colors.panel,
        marginBottom: 6,
      }}
    >
      <Text style={[styles.text, { fontWeight: "700" }]}>
        {characterName} · {deck.name}
      </Text>
      {deck.note ? <Text style={styles.muted}>{deck.note}</Text> : null}
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
 * 대전 만들기: 내 덱과 상대 덱을 고르고 AI 또는 친구와 대전한다.
 * 덱은 서버에 저장된(동기화된) 덱만 쓸 수 있다. 대전 화면은 WebView(/play)로 연다.
 */
export default function Battle() {
  const { decks, catalog, language, user, t } = useApp();
  const [mine, setMine] = useState<number | null>(null);
  const [rivalSource, setRivalSource] = useState<"same" | "mine" | "public">("same");
  const [rival, setRival] = useState<number | null>(null);
  const [opponent, setOpponent] = useState<Opponent>("ai");
  const [mode, setMode] = useState<BattleMode>("automatic");
  const [readyTimer, setReadyTimer] = useState(0);
  const [effectTimer, setEffectTimer] = useState(0);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PublicDeck[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [invite, setInvite] = useState<{ p1: string; p2: string } | null>(null);
  const [resume, setResume] = useState<LastBattle | null>(null);

  useFocusEffect(
    React.useCallback(() => {
      lastBattle().then(setResume);
    }, []),
  );

  const characterName = (id: number) =>
    catalog?.characters.find((c) => c.id === id)?.localized?.[language]?.name ?? `#${id}`;

  // 서버 id가 있는(동기화된) 덱만 대전에 쓸 수 있다.
  const synced: DeckOption[] = useMemo(
    () =>
      decks
        .filter((deck) => deck.id && !deck.deleted)
        .map((deck) => ({ id: deck.id!, name: deck.name, character_id: deck.character_id })),
    [decks],
  );
  const unsynced = decks.filter((deck) => !deck.id && !deck.deleted).length;

  useEffect(() => {
    if (rivalSource !== "public") return;
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
  }, [query, rivalSource]);

  const chooseOpponent = (value: Opponent) => {
    setOpponent(value);
    if (value === "ai") setMode("automatic");
    setReadyTimer(value === "human" ? 30 : 0);
    setEffectTimer(value === "human" ? 60 : 0);
  };

  const rivalDeck = rivalSource === "same" ? mine : rival;

  const start = async () => {
    if (!mine || !rivalDeck) return;
    setBusy(true);
    setError("");
    try {
      const session = await createBattle({
        p1_deck: mine,
        p2_deck: rivalDeck,
        opponent,
        mode,
        ready_timeout_seconds: readyTimer,
        effect_timeout_seconds: effectTimer,
      });
      const label = `${characterName(synced.find((d) => d.id === mine)?.character_id ?? 0)} · ${
        opponent === "ai" ? "AI 대전" : mode === "manual" ? "수동 대전" : "친구 대전"
      }`;
      await rememberBattle(session.urls.p1, label);
      if (session.urls.p2) {
        setInvite({ p1: session.urls.p1, p2: session.urls.p2 });
        return;
      }
      router.push({ pathname: "/play", params: { url: session.urls.p1 } });
    } catch (exception) {
      setError(errorText(exception));
    } finally {
      setBusy(false);
    }
  };

  if (invite) {
    return (
      <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 40 }}>
        <View style={styles.panel}>
          <Text style={styles.title}>{t("친구 초대")}</Text>
          <Text style={[styles.text, { marginBottom: 12 }]}>
            {t("상대 좌석 주소를 친구에게 보내세요. 친구는 브라우저나 앱 없이도 이 주소로 참가할 수 있습니다.")}
          </Text>
          <Text selectable style={[styles.muted, { marginBottom: 12 }]}>
            {invite.p2}
          </Text>
          <View style={styles.row}>
            <Button label="링크 보내기" onPress={() => Share.share({ message: invite.p2 })} />
            <Button
              label="내 좌석으로"
              onPress={() => {
                setInvite(null);
                router.push({ pathname: "/play", params: { url: invite.p1 } });
              }}
            />
          </View>
        </View>
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.screen} contentContainerStyle={{ paddingBottom: 40 }}>
      {resume && (
        <View style={[styles.panel, styles.row, { justifyContent: "space-between" }]}>
          <Text style={styles.text}>
            {t("진행 중이던 대전")} · {resume.label}
          </Text>
          <Button label="이어하기" onPress={() => router.push({ pathname: "/play", params: { url: resume.url } })} />
        </View>
      )}

      <View style={styles.panel}>
        <Text style={styles.title}>{t("내 덱")}</Text>
        {!user && <Notice text={t("로그인하고 덱을 동기화하면 내 덱으로 대전할 수 있습니다.")} />}
        {user && !synced.length && <Notice text={t("서버에 저장된 덱이 없습니다. 덱 화면에서 덱을 만들어 주세요.")} />}
        {synced.map((deck) => (
          <DeckRow
            key={deck.id}
            deck={deck}
            selected={mine === deck.id}
            characterName={characterName(deck.character_id)}
            onPress={() => setMine(deck.id)}
          />
        ))}
        {unsynced > 0 && <Text style={styles.muted}>{t(`동기화되지 않은 덱 ${unsynced}개는 대전에 쓸 수 없습니다.`)}</Text>}
      </View>

      <View style={styles.panel}>
        <Text style={styles.title}>{t("상대")}</Text>
        <Choices
          values={[
            { key: "ai", label: t("AI와 대전") },
            { key: "human", label: t("친구와 대전") },
          ]}
          value={opponent}
          onChange={(v) => chooseOpponent(v as Opponent)}
        />
        <Text style={[styles.muted, { marginBottom: 6 }]}>{t("상대 덱")}</Text>
        <Choices
          values={[
            { key: "same", label: t("같은 덱") },
            { key: "mine", label: t("내 덱") },
            { key: "public", label: t("공개 덱") },
          ]}
          value={rivalSource}
          onChange={(v) => {
            setRivalSource(v as typeof rivalSource);
            setRival(null);
          }}
        />
        {rivalSource === "mine" &&
          synced.map((deck) => (
            <DeckRow
              key={deck.id}
              deck={deck}
              selected={rival === deck.id}
              characterName={characterName(deck.character_id)}
              onPress={() => setRival(deck.id)}
            />
          ))}
        {rivalSource === "public" && (
          <>
            <Input value={query} onChangeText={setQuery} placeholder={t("덱 이름·작성자 (2글자 이상)")} />
            {results.map((deck) => (
              <DeckRow
                key={deck.id}
                deck={{ ...deck, note: deck.author?.username }}
                selected={rival === deck.id}
                characterName={characterName(deck.character_id)}
                onPress={() => setRival(deck.id)}
              />
            ))}
          </>
        )}
        {opponent === "human" && (
          <>
            <Text style={[styles.muted, { marginBottom: 6 }]}>{t("대전 방식")}</Text>
            <Choices
              values={[
                { key: "automatic", label: t("자동 판정") },
                { key: "manual", label: t("수동(샌드박스)") },
              ]}
              value={mode}
              onChange={(v) => setMode(v as BattleMode)}
            />
          </>
        )}
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
      </View>

      {error ? <Notice text={error} /> : null}
      <Button label={busy ? "만드는 중…" : "대전 시작"} disabled={busy || !mine || !rivalDeck} onPress={start} />
    </ScrollView>
  );
}
