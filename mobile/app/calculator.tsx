import { userMessage } from "../src/errors";
import React, { Suspense, useEffect, useRef, useState } from "react";
import {
  ScrollView,
  View,
  Text,
  Pressable,
  Share,
  AppState,
  BackHandler,
  StyleSheet,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useApp } from "../src/provider";
import type { Action, CalcState } from "../src/types";
import { localized, newCalculator, reduceCalculator } from "../src/core";
import { preference, saveCalculator } from "../src/storage";
import { request, absoluteUrl } from "../src/api";
import {
  SharedCalculator,
  SharedSession,
  saveShared,
  storedShared,
  parseShareLink,
} from "../src/shared";
import { calculatorUi, calculatorLink } from "../src/calculator-ui";
const CharacterCalculatorBoard = React.lazy(
  () => import("../src/calculator-character-board"),
);
import { HpQueue, type PendingHp } from "../src/hp-queue";
import {
  PassiveInputQueue,
  isPassiveInput,
  projectPassiveInputs,
} from "../src/calculator-passive-queue";
import {
  styles,
  Badge,
  Button,
  Chip,
  IconButton,
  Input,
  Notice,
  Segmented,
  colors,
} from "../src/ui";
import { CharacterGrid, PlayerSlot, Versus } from "../src/character-picker";
import { SettingColumn, SettingRow, SettingSection } from "../src/setting-rows";
import { characterWithTrait } from "../src/deck-rules";
import { TournamentCalculatorControls } from "../src/tournament-calculator-controls";

export default function Calculator() {
  const params = useLocalSearchParams<{
    party?: string;
    tournament?: string;
    ui?: string;
  }>();
  const { catalog, language, t, online, user, scope } = useApp();
  const ui = calculatorUi(params.ui);
  const Board = CharacterCalculatorBoard;
  const [local, setLocal] = useState<CalcState | null>(null),
    [shared, setShared] = useState<CalcState | null>(null),
    [session, setSession] = useState<SharedSession | null>(null),
    [mode, setMode] = useState("local");
  const [connected, setConnected] = useState(false),
    [busy, setBusy] = useState(false),
    [link, setLink] = useState(""),
    [error, setError] = useState(""),
    [p1, setP1] = useState(""),
    [p2, setP2] = useState(""),
    [now, setNow] = useState(Date.now()),
    [settings, setSettings] = useState(false),
    [picking, setPicking] = useState<"p1" | "p2" | null>(null),
    [gridWidth, setGridWidth] = useState(0),
    [ready, setReady] = useState(false);
  const [p1Trait, setP1Trait] = useState(""),
    [p2Trait, setP2Trait] = useState("");
  const [pendingHp, setPendingHp] = useState<PendingHp>({ p1: 0, p2: 0 });
  const [pendingFp, setPendingFp] = useState<PendingHp>({ p1: 0, p2: 0 });
  const [pendingShield, setPendingShield] = useState<PendingHp>({
    p1: 0,
    p2: 0,
  });
  const hpQueue = useRef<HpQueue | null>(null);
  const passiveQueue = useRef<PassiveInputQueue | null>(null);
  const [pendingPassives, setPendingPassives] = useState<Action[]>([]);
  const sharedBusy = useRef(false);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const client = useRef<SharedCalculator | null>(null),
    localRef = useRef(local);
  localRef.current = local;
  const partyCompleted = useRef<boolean | null>(null);
  useEffect(() => {
    const completed = shared?.party?.completed;
    if (mode === "shared" && completed !== undefined) {
      if (
        completed &&
        partyCompleted.current === false &&
        session?.control_token
      )
        router.dismissTo("/party");
      partyCompleted.current = completed;
    }
  }, [shared?.party?.completed, mode]);
  useEffect(() => {
    let live = true;
    Promise.all([
      preference<CalcState | null>("local-calculator", null),
      storedShared(),
    ])
      .then(([saved, sharedSession]) => {
        if (!live) return;
        localRef.current = saved;
        setLocal(saved);
        const usable =
          !sharedSession?.tournament ||
          sharedSession.tournament.user_id === user?.id;
        setSession(usable ? sharedSession : null);
        if (
          ((params.party && !sharedSession?.tournament) ||
            (params.tournament && sharedSession?.tournament)) &&
          sharedSession &&
          usable
        )
          setMode("shared");
        setReady(true);
      })
      .catch((err) => {
        if (live) {
          setError(userMessage(err));
          setReady(true);
        }
      });
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, []);
  useEffect(() => {
    if (session) {
      client.current = new SharedCalculator(
        session,
        language,
        setShared,
        setConnected,
      );
    }
    return () => {
      client.current?.dispose();
      client.current = null;
      setConnected(false);
    };
  }, [session, language, scope]);
  useEffect(() => {
    if (session?.tournament && session.tournament.user_id !== user?.id) {
      client.current?.dispose();
      client.current = null;
      setShared(null);
      setSession(null);
      router.replace("/tournaments");
    }
  }, [scope, session]);
  const baseState =
    session?.tournament && session.tournament.user_id !== user?.id
      ? null
      : mode === "shared"
        ? shared
        : local;
  const state = projectPassiveInputs(baseState, pendingPassives);
  useEffect(() => {
    if (!state?.party && state?.type !== "tournament" && !params.tournament)
      return;
    const subscription = BackHandler.addEventListener(
      "hardwareBackPress",
      () => {
        void flushInputs().then(() => returnToTournamentOrParty());
        return true;
      },
    );
    return () => subscription.remove();
  }, [state?.party?.code, state?.tournament?.id]);
  function returnToTournamentOrParty() {
    if (session?.tournament)
      router.dismissTo({
        pathname: "/tournament/[id]",
        params: { id: String(session.tournament.tournament_id) },
      });
    else router.dismissTo(params.tournament ? "/tournaments" : "/party");
  }
  async function commitAction(value: Action) {
    if (mode === "shared" && sharedBusy.current) return;
    const sharedAction = mode === "shared";
    try {
      setError("");
      if (value.action === "undo") {
        const pending = hpQueue.current?.hasPendingHp;
        hpQueue.current?.clear("hp");
        if (pending) return;
      }
      if (["reset_session", "sudden_death"].includes(value.action))
        hpQueue.current?.clear();
      if (value.action === "fp_reset")
        hpQueue.current?.clear("fp", value.target);
      if (value.action === "shield_reset") await hpQueue.current?.flush();
      if (mode === "shared") {
        sharedBusy.current = true;
        hpQueue.current?.setBusy(true);
        passiveQueue.current?.setBusy(true);
        setBusy(true);
        await client.current?.send(value);
      } else if (localRef.current) {
        const next = reduceCalculator(localRef.current, value);
        localRef.current = next;
        setLocal(next);
        await saveCalculator(next);
      }
    } catch (err) {
      setError(userMessage(err));
      if (value.action === "preparation") throw err;
    } finally {
      if (sharedAction) {
        sharedBusy.current = false;
        setBusy(false);
        hpQueue.current?.setBusy(false);
        passiveQueue.current?.setBusy(false);
      }
    }
  }
  async function flushInputs() {
    await passiveQueue.current?.flush();
    await hpQueue.current?.flush();
  }
  async function action(value: Action) {
    if (isPassiveInput(value)) {
      if (!availableRef.current) return;
      await hpQueue.current?.flush();
      passiveQueue.current?.add(value);
      return;
    }
    if (["reset_session", "sudden_death"].includes(value.action))
      passiveQueue.current?.clear();
    await passiveQueue.current?.flush();
    await commitAction(value);
  }
  const commitRef = useRef(commitAction);
  commitRef.current = commitAction;
  const actionRef = useRef(action);
  actionRef.current = action;
  useEffect(() => {
    const passives = new PassiveInputQueue(
      (value) => commitRef.current(value),
      setPendingPassives,
      undefined,
      (err) => setError(userMessage(err)),
    );
    passiveQueue.current = passives;
    const queue = new HpQueue(
      (value) => actionRef.current(value),
      (hp, fp, shield) => {
        setPendingHp(hp);
        setPendingFp(fp);
        setPendingShield(shield);
      },
      undefined,
      (err) => setError(userMessage(err)),
    );
    hpQueue.current = queue;
    const subscription = AppState.addEventListener("change", (phase) => {
      if (phase !== "active") {
        if (modeRef.current === "local")
          void passives.flush().then(() => queue.flush());
        else {
          passives.clear();
          queue.clear();
        }
      }
    });
    return () => {
      subscription.remove();
      if (modeRef.current === "local")
        void passives
          .flush()
          .then(() => queue.flush())
          .finally(() => {
            passives.dispose();
            queue.dispose();
          });
      else {
        passives.dispose();
        queue.dispose();
      }
    };
  }, []);
  const available =
    !!state?.can_control &&
    !state.is_expired &&
    (mode !== "shared" || (connected && online)) &&
    !(
      state?.type === "tournament" &&
      !state.sudden_death &&
      state.round_timer?.ends_at &&
      Date.parse(state.round_timer.ends_at) <= now
    );
  const availableRef = useRef(available);
  availableRef.current = available;
  useEffect(() => {
    hpQueue.current?.setAvailable(available);
    passiveQueue.current?.setAvailable(available);
  }, [available]);
  const hpScope = `${mode}:${session?.view_token || ""}:${state?.set?.current_number || ""}:${state?.players.p1.character?.id || ""}:${state?.players.p2.character?.id || ""}`;
  useEffect(() => {
    hpQueue.current?.clear();
    passiveQueue.current?.clear();
  }, [hpScope]);
  async function changeMode(next: string) {
    if (modeRef.current === "local") await flushInputs();
    else {
      passiveQueue.current?.clear();
      hpQueue.current?.clear();
    }
    setMode(next);
  }
  function selected() {
    const a = catalog?.characters.find(
        (c) =>
          String(c.id) ===
          (p1 ||
            String(
              catalog.characters.find((c) => c.traits?.length)?.id ||
                catalog.characters[0]?.id,
            )),
      ),
      b = catalog?.characters.find(
        (c) =>
          String(c.id) ===
          (p2 ||
            String(
              catalog.characters.find((c) => c.traits?.length)?.id ||
                catalog.characters[0]?.id,
            )),
      );
    if (!a || !b) throw new Error("캐릭터를 선택해주세요.");
    return [
      characterWithTrait(a, Number(p1Trait) || null),
      characterWithTrait(b, Number(p2Trait) || null),
    ] as const;
  }
  async function create(sharedMode: boolean) {
    try {
      passiveQueue.current?.clear();
      await passiveQueue.current?.flush();
      hpQueue.current?.clear();
      const [a, b] = selected();
      if (sharedMode) {
        const result = await request(
          "/calculators/",
          {
            method: "POST",
            body: JSON.stringify({
              schema_version: 2,
              player1_trait_card_id: (a as any).selected_trait_id,
              player2_trait_card_id: (b as any).selected_trait_id,
              player1_character: a.id,
              player2_character: b.id,
            }),
          },
          false,
        );
        const next = {
          view_token: result.view_token,
          control_token: result.control_token,
        };
        await saveShared(next);
        setSession(next);
        setShared(result.state);
        setMode("shared");
      } else {
        const next = newCalculator(a, b, language);
        localRef.current = next;
        setLocal(next);
        await saveCalculator(next);
        setMode("local");
      }
      setError("");
      return true;
    } catch (err) {
      setError(userMessage(err));
      return false;
    }
  }
  const disabled =
    state?.preparation?.status === "editing" ||
    busy ||
    !state?.can_control ||
    (mode === "shared" && (!connected || !online)) ||
    !!state?.is_expired ||
    !available;
  function openSettings() {
    setP1(
      String(
        state?.players.p1.character?.id || catalog?.characters[0]?.id || "",
      ),
    );
    setP2(
      String(
        state?.players.p2.character?.id || catalog?.characters[0]?.id || "",
      ),
    );
    setPicking(null);
    setSettings(true);
  }
  const defaultId = String(
    catalog?.characters.find((c) => c.traits?.length)?.id ||
      catalog?.characters[0]?.id ||
      "",
  );
  const p1Id = p1 || defaultId,
    p2Id = p2 || defaultId;
  const p1Character = catalog?.characters.find((c) => String(c.id) === p1Id);
  const p2Character = catalog?.characters.find((c) => String(c.id) === p2Id);
  if (params.tournament && (!user || !session?.tournament || !state)) {
    return (
      <View
        style={[
          styles.screen,
          { justifyContent: "center", alignItems: "center" },
        ]}
      >
        <Notice
          text={
            error ||
            (!user
              ? "참가한 대회를 확인하려면 로그인해주세요."
              : ready && !session?.tournament
                ? "내 대회에서 경기를 선택해주세요."
                : "대회 계산기에 연결 중입니다.")
          }
        />
        <Button label="대회로 돌아가기" onPress={returnToTournamentOrParty} />
      </View>
    );
  }
  return (
    <Suspense
      fallback={
        <View style={styles.screen}>
          <Notice text={t("불러오는 중")} />
        </View>
      }
    >
      <Board
        state={state}
        mode={mode}
        disabled={disabled}
        connected={connected && online}
        now={now}
        error={error}
        ready={ready}
        setupOpen={ready && (settings || !state)}
        onSetup={openSettings}
        onCloseSetup={() => {
          if (!state && local) {
            setMode("local");
            setSettings(false);
          } else if (!state) router.dismissTo("/");
          else setSettings(false);
        }}
        onShare={() => {
          openSettings();
          void changeMode("shared");
        }}
        onAction={action}
        onTournamentReturn={() => {
          void flushInputs().then(returnToTournamentOrParty);
        }}
        tournamentControls={
          state?.type === "tournament" ? (
            <TournamentCalculatorControls
              state={state}
              now={now}
              busy={busy}
              connected={connected && online}
              onAction={async (value) => {
                await flushInputs();
                await action(value);
              }}
              onResults={() => {
                void flushInputs().then(returnToTournamentOrParty);
              }}
            />
          ) : null
        }
        onPartyReturn={() => {
          void flushInputs().then(() => router.dismissTo("/party"));
        }}
        onPartyComplete={() => {
          void flushInputs().then(() =>
            action({
              action: "party_exchange",
              expected_exchange: state?.party?.exchanges,
            }),
          );
        }}
        pendingHp={pendingHp}
        pendingFp={pendingFp}
        pendingShield={pendingShield}
        onShield={(target, amount) => {
          if (availableRef.current)
            void passiveQueue.current
              ?.flush()
              .then(() => hpQueue.current?.add(target, amount, "shield"));
        }}
        onFp={(target, amount) => {
          if (availableRef.current) {
            void passiveQueue.current?.flush().then(() => {
              hpQueue.current?.setAvailable(availableRef.current);
              hpQueue.current?.add(target, amount, "fp");
            });
          }
        }}
        onHp={(target, amount) => {
          if (availableRef.current) {
            void passiveQueue.current?.flush().then(() => {
              hpQueue.current?.setAvailable(availableRef.current);
              hpQueue.current?.add(target, amount);
            });
          }
        }}
        setup={
          <SettingColumn>
            <SettingSection title="계산기">
              <SettingRow
                title="계산기 방식"
                description={
                  mode === "local"
                    ? "이 기기에서만 기록합니다. 인터넷이 없어도 됩니다."
                    : "링크로 다른 기기와 같은 계산기를 함께 보고 조작합니다."
                }
              >
                <View style={{ width: 240 }}>
                  <Segmented
                    value={mode}
                    onChange={changeMode}
                    values={[
                      {
                        key: "local",
                        label: "로컬",
                        icon: "phone-portrait-outline",
                      },
                      { key: "shared", label: "공유", icon: "people-outline" },
                    ]}
                  />
                </View>
              </SettingRow>
            </SettingSection>
            <SettingSection title="플레이어">
              {picking ? (
                <View style={{ marginBottom: 16 }}>
                  <View style={setupStyles.pickHeader}>
                    <IconButton
                      icon="chevron-back"
                      label="뒤로"
                      onPress={() => setPicking(null)}
                    />
                    <Text style={setupStyles.pickTitle}>
                      {t(picking === "p1" ? "플레이어1" : "플레이어2") +
                        " · " +
                        t("캐릭터 선택")}
                    </Text>
                  </View>
                  <View
                    onLayout={(event) =>
                      setGridWidth(event.nativeEvent.layout.width)
                    }
                  >
                    {gridWidth > 0 && (
                      <CharacterGrid
                        characters={catalog?.characters || []}
                        value={picking === "p1" ? p1Id : p2Id}
                        width={gridWidth}
                        size={56}
                        onChange={(id) => {
                          if (picking === "p1") {
                            setP1(id);
                            setP1Trait("");
                          } else {
                            setP2(id);
                            setP2Trait("");
                          }
                          setPicking(null);
                        }}
                      />
                    )}
                  </View>
                </View>
              ) : (
                <View style={setupStyles.versusRow}>
                  {(["p1", "p2"] as const).map((side) => {
                    const character = side === "p1" ? p1Character : p2Character;
                    const trait = side === "p1" ? p1Trait : p2Trait;
                    const setTrait = side === "p1" ? setP1Trait : setP2Trait;
                    const slot = (
                      <PlayerSlot
                        key={side}
                        label={side === "p1" ? "플레이어1" : "플레이어2"}
                        character={character}
                        accent={side === "p1" ? "#5fc8c0" : colors.accent}
                        onPress={() => setPicking(side)}
                      >
                        {!!character?.traits?.length && (
                          <View style={setupStyles.traits}>
                            {character.traits.map((item) => (
                              <Chip
                                key={item.id}
                                label={localized(item, language) || item.name}
                                selected={trait === String(item.id)}
                                onPress={() =>
                                  setTrait(
                                    trait === String(item.id)
                                      ? ""
                                      : String(item.id),
                                  )
                                }
                              />
                            ))}
                          </View>
                        )}
                      </PlayerSlot>
                    );
                    return side === "p1" ? (
                      slot
                    ) : (
                      <React.Fragment key="p2">
                        <Versus />
                        {slot}
                      </React.Fragment>
                    );
                  })}
                </View>
              )}
              <Button
                label={state ? "새 계산기 시작" : "시작"}
                icon="play"
                variant="primary"
                block
                disabled={
                  !ready ||
                  !catalog?.characters.length ||
                  (mode === "shared" && !online)
                }
                onPress={async () => {
                  if (await create(mode === "shared")) setSettings(false);
                }}
              />
            </SettingSection>
            {mode === "shared" && (
              <SettingSection title="공유">
                {!!session && (
                  <SettingRow
                    title="연결 상태"
                    description={
                      connected && online
                        ? "다른 기기와 실시간으로 맞춰집니다."
                        : "다시 연결하는 동안 조작이 잠깁니다."
                    }
                  >
                    <Badge
                      label={connected && online ? "연결됨" : "재연결 중"}
                      tone={connected && online ? "success" : "danger"}
                    />
                  </SettingRow>
                )}
                <SettingRow
                  title="링크로 참여"
                  description="받은 공유 링크를 붙여 넣고 참여합니다."
                  below={
                    <View style={setupStyles.linkRow}>
                      <View style={{ flex: 1 }}>
                        <Input
                          accessibilityLabel={t("공유 링크")}
                          value={link}
                          onChangeText={setLink}
                          placeholder={t("공유 링크")}
                          autoCapitalize="none"
                          autoCorrect={false}
                          style={{ marginBottom: 0 }}
                        />
                      </View>
                      <Button
                        label="참여"
                        icon="enter-outline"
                        disabled={!online || !link.trim()}
                        onPress={async () => {
                          try {
                            const next = parseShareLink(link);
                            await saveShared(next);
                            setSession(next);
                            setShared(null);
                            setError("");
                          } catch (err) {
                            setError(userMessage(err));
                          }
                        }}
                      />
                    </View>
                  }
                />
                {session && (
                  <>
                    <SettingRow
                      title="링크 보내기"
                      description="조회 링크는 보기만, 제어 링크는 HP·FP 조작까지 할 수 있습니다."
                    >
                      <View style={setupStyles.buttons}>
                        <Button
                          label="조회 링크"
                          icon="eye-outline"
                          size="sm"
                          onPress={() =>
                            Share.share({
                              message: absoluteUrl(
                                calculatorLink(
                                  "/battlelog/session/" +
                                    session.view_token +
                                    "/",
                                  ui,
                                ),
                              ),
                            })
                          }
                        />
                        {!!session.control_token && (
                          <Button
                            label="제어 링크"
                            icon="game-controller-outline"
                            size="sm"
                            onPress={() =>
                              Share.share({
                                message: absoluteUrl(
                                  calculatorLink(
                                    "/battlelog/session/" +
                                      session.view_token +
                                      "/control/" +
                                      session.control_token +
                                      "/",
                                    ui,
                                  ),
                                ),
                              })
                            }
                          />
                        )}
                      </View>
                    </SettingRow>
                    <SettingRow
                      title="공유 계산기 나가기"
                      description="이 기기에서 연결만 끊습니다. 계산기 기록은 남습니다."
                      danger
                    >
                      <Button
                        label="나가기"
                        icon="exit-outline"
                        danger
                        size="sm"
                        onPress={async () => {
                          await saveShared(null);
                          setSession(null);
                          setShared(null);
                        }}
                      />
                    </SettingRow>
                  </>
                )}
              </SettingSection>
            )}
          </SettingColumn>
        }
      />
    </Suspense>
  );
}

const setupStyles = StyleSheet.create({
  versusRow: {
    flexDirection: "row",
    alignItems: "stretch",
    gap: 12,
    marginBottom: 16,
  },
  traits: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 6,
  },
  pickHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginBottom: 8,
  },
  pickTitle: { color: colors.text, fontSize: 17, fontWeight: "700" },
  linkRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  buttons: { flexDirection: "row", gap: 8 },
});
