import React, { useCallback, useEffect, useRef, useState } from "react";
import { Image as TileImage } from "expo-image";
import {
  AppState,
  Image,
  Pressable,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import { absoluteUrl } from "../src/api";
import { userMessage } from "../src/errors";
import { saveShared } from "../src/shared";
import {
  partyRequest,
  saveParty,
  storedParty,
  type PartySeat,
  type PartyState,
  type PartyTile,
} from "../src/party";
import { Button, Choices, Input, Notice, colors, styles } from "../src/ui";
import { PartyBoard3D } from "../src/party-board-3d";
import { partyRollStage } from "../src/party-roll";
import { partyEventStage } from "../src/party-event";
import { PartyCardPreview } from "../src/party-card";
import { PartyHand } from "../src/party-hand";
import {
  PartyArrivalChoice,
  type ArrivalChoiceKind,
} from "../src/party-arrival-choice";
import {
  PartyItemPicker,
  type PartyItemChoice,
} from "../src/party-item-picker";
import {
  PartyRoster,
  PartyMove,
  PartySelection,
  PartyDuel,
  PartyRoll,
  PartyEvent,
} from "../src/party-hud";

import { useCalculatorEntry } from "../src/calculator-entry";
import { PartySupplyChoice } from "../src/party-supply-choice";

const pawnColors = ["#e4b76a", "#87c9e4", "#c2a0ea", "#91d4ab"];
export default function Party() {
  const { catalog, language, online, t } = useApp();
  const { chooseUi, entrySheet } = useCalculatorEntry();
  const [state, setState] = useState<PartyState | null>(null);
  const [seat, setSeat] = useState<PartySeat | null>(null);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [roomName, setRoomName] = useState("루멘 파티");
  const [characterId, setCharacterId] = useState("");
  const [interactionSeq, setInteractionSeq] = useState(0);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<PartyTile | null>(null);
  const [routeTarget, setRouteTarget] = useState<number | null>(null);
  const [releasedEncounter, setReleasedEncounter] = useState("");
  const [itemChoice, setItemChoice] = useState<PartyItemChoice | null>(null);
  const [inventoryDragging, setInventoryDragging] = useState(false);
  const gameBoardRef = useRef<View>(null);
  const [cardPreview, setCardPreview] = useState<string | null>(null);
  const [cameraRequest, setCameraRequest] = useState<{
    seat: number;
    id: number;
  } | null>(null);
  const [movementHold, setMovementHold] = useState<{
    version: number;
    previous: PartyState;
  } | null>(null);
  const finishMovement = useCallback(
    (version: number) =>
      setMovementHold((current) =>
        current && current.version <= version ? null : current,
      ),
    [],
  );
  const visibleState =
    state && movementHold
      ? {
          ...state,
          players: movementHold.previous.players,
          event: movementHold.previous.event,
          log: movementHold.previous.log,
          me: movementHold.previous.me,
        }
      : state;
  const scroll = useRef<ScrollView>(null);
  const boardTop = useRef(0);
  function focusPlayer(seat: number) {
    setCameraRequest((current) => ({ seat, id: (current?.id || 0) + 1 }));
    setInteractionSeq((value) => value + 1);
    scroll.current?.scrollTo({ y: boardTop.current, animated: true });
  }
  useEffect(() => {
    if (
      !state?.can_use_items ||
      (itemChoice && !state.me?.items.includes(itemChoice.item))
    )
      setItemChoice(null);
  }, [state, itemChoice]);
  useEffect(
    () => setRouteTarget(null),
    [state?.code, state?.move?.roll_version, !!state?.move],
  );
  const stateRef = useRef(state);
  stateRef.current = state;
  const seatRef = useRef(seat);
  seatRef.current = seat;
  const busyRef = useRef(false);
  const pollRef = useRef(false);
  const choosingRoom = useRef(false);
  const focused = useRef(false);
  const serverOffset = useRef(0);
  const [, tickRoll] = useState(0);
  const rollStage = partyRollStage(state, Date.now() + serverOffset.current);
  const eventStage = partyEventStage(state, Date.now() + serverOffset.current);
  useEffect(() => {
    if (
      !partyRollStage(stateRef.current, Date.now() + serverOffset.current) &&
      !partyEventStage(stateRef.current, Date.now() + serverOffset.current)
    )
      return;
    const timer = setInterval(() => {
      tickRoll((value) => value + 1);
      if (
        !partyRollStage(stateRef.current, Date.now() + serverOffset.current) &&
        !partyEventStage(stateRef.current, Date.now() + serverOffset.current)
      )
        clearInterval(timer);
    }, 50);
    return () => clearInterval(timer);
  }, [
    state?.code,
    state?.dice_roll?.version,
    state?.event?.version,
    state?.event?.pending,
    state?.status,
    state?.expired,
  ]);

  function accept(next: PartyState) {
    const previous = stateRef.current;
    if (
      previous?.code === next.code &&
      (next.version < previous.version ||
        (next.version === previous.version &&
          next.battle &&
          previous.battle &&
          next.battle.version < previous.battle.version))
    )
      return;
    const receipt = next.move_path;
    if (
      previous?.code !== next.code ||
      previous?.me?.seat !== next.me?.seat ||
      next.battle
    )
      setMovementHold(null);
    else if (
      receipt &&
      receipt.version !== previous?.move_path?.version &&
      receipt.nodes.length > 1 &&
      !receipt.teleport
    )
      setMovementHold((current) => ({
        version: receipt.version,
        previous: current?.previous || previous!,
      }));
    stateRef.current = next;
    serverOffset.current = (next.server_time || Date.now()) - Date.now();
    setState(next);
  }
  async function openCalculator(next: PartyState) {
    const battle = next.battle;
    if (!battle) return;
    if (seatRef.current) {
      const saved = { ...seatRef.current, openedBattle: battle.id };
      await saveParty(saved);
      seatRef.current = saved;
      setSeat(saved);
    }
    const ui = await chooseUi();
    if (!ui || stateRef.current?.battle?.id !== battle.id) return;
    await saveShared({
      view_token: battle.view_token,
      control_token: battle.control_token || "",
    });
    router.push({ pathname: "/calculator", params: { party: "1", ui } });
  }
  async function refresh(saved = seatRef.current, autoOpen = true) {
    if (!saved || pollRef.current) return;
    pollRef.current = true;
    try {
      const next: PartyState = await partyRequest(
        saved.code + "/state",
        saved.token,
      );
      if (
        saved.code !== seatRef.current?.code ||
        saved.token !== seatRef.current?.token ||
        choosingRoom.current ||
        !focused.current
      )
        return;
      accept(next);
      setConnected(true);
      if (
        autoOpen &&
        next.battle?.control_token &&
        !next.battle.completed &&
        seatRef.current?.openedBattle !== next.battle.id &&
        !busyRef.current
      )
        await openCalculator(next);
    } catch (err) {
      if (
        saved.code !== seatRef.current?.code ||
        saved.token !== seatRef.current?.token
      )
        return;
      setConnected(false);
      setError(userMessage(err));
    } finally {
      pollRef.current = false;
    }
  }
  useFocusEffect(
    useCallback(() => {
      let live = true;
      focused.current = true;
      void storedParty()
        .then((saved) => {
          if (!live || !saved || choosingRoom.current) return;
          seatRef.current = saved;
          setSeat(saved);
          setCode(saved.code);
          void refresh(saved);
        })
        .catch((err) => {
          if (live) setError(userMessage(err));
        });
      const timer = setInterval(() => {
        if (
          live &&
          AppState.currentState === "active" &&
          !busyRef.current &&
          !choosingRoom.current
        )
          void refresh();
      }, 1000);
      return () => {
        live = false;
        focused.current = false;
        clearInterval(timer);
      };
    }, []),
  );

  async function enter(create: boolean) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const selectedId = Number(characterId || catalog?.characters[0]?.id);
      if (!selectedId) throw new Error("캐릭터 데이터를 먼저 받아주세요.");
      const result = await partyRequest(
        create ? "" : code.trim().toUpperCase() + "/join",
        "",
        {
          name,
          character_id: selectedId,
          room_name: roomName,
        },
      );
      const saved = { code: result.state.code, token: result.token };
      choosingRoom.current = false;
      await saveParty(saved);
      seatRef.current = saved;
      setSeat(saved);
      setCode(saved.code);
      accept(result.state);
      setConnected(true);
      setError("");
    } catch (err) {
      setError(userMessage(err));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function act(action: string, data: Record<string, unknown> = {}) {
    if (
      !stateRef.current ||
      !seatRef.current ||
      busyRef.current ||
      !connected ||
      !online
    )
      return;
    if (action === "roll")
      scroll.current?.scrollTo({ y: boardTop.current, animated: true });
    busyRef.current = true;
    setBusy(true);
    if (action === "challenge" || action === "counterattack")
      setReleasedEncounter("");
    try {
      const result = await partyRequest(
        seatRef.current.code + "/action",
        seatRef.current.token,
        { action, expected_version: stateRef.current.version, ...data },
      );
      accept(result.state);
      setError("");
      if (action === "challenge" || action === "counterattack")
        await openCalculator(result.state);
    } catch (err) {
      setError(userMessage(err));
      await refresh(seatRef.current, false);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function switchTestPlayer(value: string) {
    const current = stateRef.current;
    if (!current?.test_controls || busyRef.current || !connected || !online)
      return;
    busyRef.current = true;
    setBusy(true);
    try {
      const result = await partyRequest(
        current.code + "/test-seat",
        seatRef.current?.token || "",
        { seat: value === "spectator" ? value : Number(value) },
      );
      const saved = {
        code: current.code,
        token: result.token,
        openedBattle: result.state.battle?.id,
      };
      seatRef.current = saved;
      setSeat(saved);
      await saveParty(saved);
      setSelected(null);
      setRouteTarget(null);
      setItemChoice(null);
      setReleasedEncounter("");
      stateRef.current = null;
      accept(result.state);
      setConnected(true);
      setError("");
    } catch (err) {
      setError(userMessage(err));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  const player = state?.players.find((p) => p.seat === state.me?.seat);
  const turn =
    !!state &&
    state.status === "running" &&
    state.turn === state.me?.seat &&
    !state.battle;
  const tile = player && state?.board.nodes[player.position];
  const forward = player?.forward_exits ?? tile?.exits ?? [];
  const locked =
    busy || !online || !connected || !!state?.expired || !!movementHold;
  useEffect(() => {
    if (
      !turn ||
      locked ||
      !state?.can_auto_end_turn ||
      eventStage ||
      itemChoice ||
      cardPreview ||
      inventoryDragging ||
      !focused.current
    )
      return;
    const version = state.version;
    const timer = setTimeout(() => {
      if (
        focused.current &&
        AppState.currentState === "active" &&
        !busyRef.current &&
        stateRef.current?.version === version
      )
        void act("auto_end_turn");
    }, 650);
    return () => clearTimeout(timer);
  }, [
    turn,
    locked,
    state?.can_auto_end_turn,
    state?.version,
    eventStage,
    itemChoice,
    cardPreview,
    inventoryDragging,
  ]);
  const canMove =
    !!state?.can_act &&
    !state.move?.reveal_pending &&
    !itemChoice &&
    !movementHold;
  const eventReady =
    !!state?.event?.pending &&
    Date.now() + serverOffset.current >= (state.event.reveal_until || 0);
  useEffect(() => {
    if (!eventReady || !turn || locked || !focused.current) return;
    const timer = setTimeout(() => {
      if (!busyRef.current && AppState.currentState === "active")
        void act("resolve_event", { event_version: state?.event?.version });
    }, 80);
    return () => clearTimeout(timer);
  }, [eventReady, turn, locked, state?.event?.version, state?.version]);
  const itemTargets =
    itemChoice && state?.board.shop[itemChoice.item]?.target === "tile"
      ? state.item_targets[itemChoice.item] || []
      : [];
  const advanceRef = useRef(() => {});
  advanceRef.current = () => {
    void act("advance");
  };
  useEffect(() => {
    if (
      !focused.current ||
      !turn ||
      !state?.move ||
      state.move_prompt ||
      locked ||
      !!itemChoice ||
      (state.move.reveal_pending
        ? !!rollStage
        : !canMove || forward.length !== 1)
    )
      return;
    const timer = setTimeout(() => {
      if (
        focused.current &&
        AppState.currentState === "active" &&
        !busyRef.current
      )
        advanceRef.current();
    }, 100);
    return () => clearTimeout(timer);
  }, [state, turn, canMove, locked, forward.length, rollStage, itemChoice]);
  const battlePlayers = state?.battle
    ? state.players.filter((p) =>
        [state.battle!.p1, state.battle!.p2].includes(p.seat),
      )
    : [];
  const encounterKey = `${state?.code}:${state?.turn_number}:${player?.position}:${state?.move?.roll_version || "landed"}:${state?.challenge_targets.join(",")}`;
  const counter =
    !!state?.counter_prompt && state.counter_prompt.seat === player?.seat;
  const duelTargets =
    state?.players.filter((p) =>
      counter
        ? p.seat === state.counter_prompt?.target
        : state.challenge_targets.includes(p.seat),
    ) || [];
  const showDuel =
    (counter ||
      (canMove &&
        turn &&
        !state?.counter_prompt &&
        !state?.item_reward &&
        !state?.camp_gift &&
        !state?.challenge_declined)) &&
    duelTargets.length > 0 &&
    (counter || releasedEncounter !== encounterKey) &&
    !state?.battle;

  const choiceKind: ArrivalChoiceKind | null = state?.camp_gift
    ? "camp_gift"
    : state?.supply_encounter
      ? null
      : state?.move_prompt?.own_camp || state?.move_prompt?.shared_camp
        ? "camp_pass"
        : state?.can_transfer
          ? "transfer"
          : state?.can_charge
            ? "charge"
            : state?.can_buy_item
              ? "shop"
              : null;
  const automaticAction =
    state?.arrival === "dash" && !state.move && !state.landed
      ? "roll"
      : state?.can_buy_crystal &&
          player &&
          player.crystals < 3 &&
          player.coins >= state.board.crystal_costs[player.crystals]!
        ? "buy_crystal"
        : null;
  useEffect(() => {
    if (
      !automaticAction ||
      !canMove ||
      locked ||
      showDuel ||
      state?.item_reward ||
      state?.camp_gift ||
      state?.supply_encounter ||
      inventoryDragging ||
      cardPreview ||
      !focused.current
    )
      return;
    const version = state?.version;
    const timer = setTimeout(() => {
      if (
        focused.current &&
        AppState.currentState === "active" &&
        !busyRef.current &&
        stateRef.current?.version === version
      )
        void act(automaticAction);
    }, 150);
    return () => clearTimeout(timer);
  }, [
    automaticAction,
    canMove,
    locked,
    showDuel,
    state?.version,
    state?.item_reward,
    state?.camp_gift,
    inventoryDragging,
    cardPreview,
  ]);

  return (
    <ScrollView
      scrollEnabled={!inventoryDragging}
      ref={scroll}
      onTouchStart={() => setInteractionSeq((value) => value + 1)}
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      {entrySheet}
      <Notice text={error} />
      {!state ? (
        <View style={styles.panel}>
          <Text style={styles.title}>루멘 파티</Text>
          <Text style={[styles.text, { marginBottom: 16 }]}>
            카드는 테이블에서, 지도는 각자의 기기에서. 교전은 최대 두 번의
            공방으로 진행합니다.
          </Text>
          <Input
            value={name}
            onChangeText={setName}
            placeholder="내 이름"
            maxLength={30}
            accessibilityLabel="내 이름"
          />
          <Text style={styles.text}>캐릭터</Text>
          <ScrollView horizontal style={{ marginVertical: 12 }}>
            <Choices
              value={characterId || String(catalog?.characters[0]?.id || "")}
              onChange={setCharacterId}
              values={(catalog?.characters || []).map((c) => ({
                key: String(c.id),
                label: localized(c, language),
              }))}
            />
          </ScrollView>
          <Input
            value={roomName}
            onChangeText={setRoomName}
            placeholder="방 이름"
            maxLength={60}
            accessibilityLabel="방 이름"
          />
          <Button
            label="방 만들기"
            disabled={busy || !online || !name.trim()}
            onPress={() => void enter(true)}
          />
          <View style={{ marginTop: 24 }}>
            <Input
              value={code}
              onChangeText={(v) => setCode(v.toUpperCase())}
              placeholder="여섯 자리 방 코드"
              maxLength={6}
              autoCapitalize="characters"
              accessibilityLabel="방 코드"
            />
          </View>
          <Button
            label="파티 참여"
            disabled={busy || !online || !name.trim() || code.length !== 6}
            onPress={() => void enter(false)}
          />
          {!!seat && (
            <View style={{ marginTop: 12 }}>
              <Button
                label={`최근 파티 ${seat.code}로 복귀`}
                disabled={busy || !online}
                onPress={() => {
                  choosingRoom.current = false;
                  void refresh(seat);
                }}
              />
            </View>
          )}
        </View>
      ) : (
        <>
          {state.test_controls && (
            <View style={styles.panel}>
              <Text style={styles.title}>테스트 · 플레이어 전환</Text>
              <View
                pointerEvents={busy ? "none" : "auto"}
                style={{ opacity: busy ? 0.5 : 1 }}
              >
                <Choices
                  values={[
                    { key: "spectator", label: "관전" },
                    ...state.players.map((p) => ({
                      key: String(p.seat),
                      label: `${p.seat + 1}P · ${p.name}`,
                    })),
                  ]}
                  value={String(state.me?.seat ?? "spectator")}
                  onChange={(value) => void switchTestPlayer(value)}
                />
              </View>
            </View>
          )}
          <View style={styles.panel}>
            <Text style={styles.title}>
              {state.name} · {state.code}
            </Text>
            <Text style={styles.text}>
              {state.status === "lobby"
                ? `대기실 ${state.players.length}/4명`
                : `라운드 ${state.round}`}
            </Text>
            <Text style={[styles.muted, { marginVertical: 8 }]}>
              이동력 +{state.movement_power} · 공격자 FP +{state.attacker_bonus}
              {"\n"}
              {connected && online ? "연결됨" : "재연결 중 · 조작 잠금"}
              {state.expired ? " · 방 만료" : ""}
            </Text>
            <View style={styles.row}>
              <Button
                label="초대 공유"
                onPress={() =>
                  void Share.share({ message: absoluteUrl(state.url) })
                }
              />
              <Button
                label="다른 파티"
                disabled={busy}
                onPress={() => {
                  choosingRoom.current = true;
                  stateRef.current = null;
                  setState(null);
                }}
              />
            </View>
          </View>
          {state.status === "lobby" && player && (
            <View style={[styles.panel, styles.row]}>
              <Button
                label={player.ready ? "준비 취소" : "준비 완료"}
                disabled={locked}
                onPress={() => void act("ready")}
              />
              {state.me?.is_host && (
                <Button
                  label="파티 시작"
                  disabled={
                    locked ||
                    state.players.length < 2 ||
                    state.players.some((p) => !p.ready)
                  }
                  onPress={() => void act("start")}
                />
              )}
            </View>
          )}
          <View
            onLayout={(e) => {
              boardTop.current = e.nativeEvent.layout.y;
            }}
            ref={gameBoardRef}
            style={{
              position: "relative",
              marginBottom: 12,
              overflow: "hidden",
              borderRadius: 20,
            }}
          >
            <PartyMap
              state={state}
              selected={selected?.id}
              onSelect={(node) => {
                setSelected(node);
                if (itemChoice && itemTargets.includes(node.id))
                  setItemChoice({ ...itemChoice, node: node.id });
                setRouteTarget(
                  state.movement_preview?.nodes.includes(node.id) &&
                    state.movement_preview.routes[node.id]
                    ? node.id
                    : null,
                );
              }}
              routeTarget={routeTarget}
              itemTargets={itemTargets}
              itemTarget={itemChoice?.node}
              canMove={canMove && !locked}
              interactionSeq={interactionSeq}
              onDirectionSelect={(id) => {
                if (
                  canMove &&
                  state.move &&
                  !state.move_prompt &&
                  forward.length > 1 &&
                  forward.includes(id) &&
                  !locked
                )
                  void act("move", { node: id });
              }}
              onMovementComplete={finishMovement}
              cameraRequest={cameraRequest}
            />
            <View
              pointerEvents="box-none"
              style={{
                position: "absolute",
                inset: 0,
                opacity: rollStage || eventStage === "card" ? 0.25 : 1,
              }}
            >
              <PartyRoster state={visibleState!} onFocusPlayer={focusPlayer} />
            </View>
            {rollStage && state.dice_roll && (
              <PartyRoll
                roll={state.dice_roll}
                stage={rollStage}
                now={Date.now() + serverOffset.current}
                name={
                  state.players.find((p) => p.seat === state.dice_roll!.seat)
                    ?.name || "플레이어"
                }
              />
            )}
            {!movementHold &&
              state.event &&
              (eventStage === "card" || eventStage === "effect") && (
                <PartyEvent event={state.event} stage={eventStage} />
              )}
            {canMove &&
              !state.move &&
              !state.landed &&
              state.arrival !== "dash" &&
              !showDuel && (
                <PartyMove disabled={locked} onPress={() => void act("roll")} />
              )}
            {!!selected &&
              !showDuel &&
              !state.battle &&
              !itemChoice &&
              !rollStage &&
              eventStage !== "card" && (
                <PartySelection
                  tile={{
                    ...selected,
                    description:
                      selected.description +
                      (state.supplies?.find((s) => s.node === selected.id)
                        ? ` 보급함 HP ${state.supplies.find((s) => s.node === selected.id)!.hp}/800. 속도 오름차순으로 기술 카드를 사용해 공격할 수 있습니다. 파괴 보상: 2코인.`
                        : ""),
                  }}
                  owner={
                    selected.kind === "camp"
                      ? state.players.find((p) => p.home === selected.id)?.name
                      : undefined
                  }
                  onClose={() => {
                    setSelected(null);
                    setRouteTarget(null);
                  }}
                />
              )}
            {showDuel && player && (
              <PartyDuel
                attacker={player}
                targets={duelTargets}
                disabled={locked}
                counter={counter}
                onFight={(target) =>
                  void act(counter ? "counterattack" : "challenge", { target })
                }
                onRelease={() => {
                  if (counter) {
                    void act("skip_counter");
                    return;
                  }
                  setReleasedEncounter(encounterKey);
                  if (
                    state.move_prompt &&
                    !(
                      state.move_prompt.own_camp ||
                      state.move_prompt.shared_camp ||
                      state.move_prompt.shop ||
                      state.move_prompt.supply
                    )
                  )
                    void act("continue_move");
                  else void act("skip_challenge");
                }}
              />
            )}
            {state.me &&
              !showDuel &&
              !state.battle &&
              !itemChoice &&
              !rollStage &&
              eventStage !== "card" && (
                <PartyHand
                  state={visibleState!}
                  disabled={locked || !state.can_use_items}
                  boardRef={gameBoardRef}
                  onDragging={setInventoryDragging}
                  onChoose={(item) => {
                    if (locked || !state.can_use_items) setCardPreview(item);
                    else {
                      setItemChoice({ item });
                      setSelected(null);
                    }
                  }}
                  onUse={(item) => {
                    if (locked || !state.can_use_items) return;
                    if (state.board.shop[item]?.target === "self")
                      void act("use_item", { item });
                    else {
                      setItemChoice({ item });
                      setSelected(null);
                    }
                  }}
                />
              )}
          </View>
          {turn &&
            player &&
            canMove &&
            !showDuel &&
            !state.item_reward &&
            !state.hand_task &&
            choiceKind && (
              <PartyArrivalChoice
                key={`${state.code}:${state.turn_number}:${player.seat}:${player.position}:${choiceKind}`}
                state={state}
                kind={choiceKind}
                disabled={locked}
                onConfirm={(value) =>
                  void act(
                    {
                      shop: "buy_item",
                      charge: "charge",
                      camp_gift: "choose_camp_gift",
                      camp_pass: "stop_home",
                      transfer: "transfer",
                    }[choiceKind],
                    choiceKind === "charge"
                      ? { target: value }
                      : { item: value },
                  )
                }
                onCancel={() =>
                  void act(
                    {
                      shop: "skip_shop",
                      charge: "skip_charge",
                      camp_gift: "skip_camp_gift",
                      camp_pass: "continue_move",
                      transfer: "skip_transfer",
                    }[choiceKind],
                  )
                }
              />
            )}
          {itemChoice && (
            <PartyItemPicker
              state={state}
              choice={itemChoice}
              disabled={locked}
              onChange={setItemChoice}
              onCancel={() => setItemChoice(null)}
              onUse={() => void act("use_item", itemChoice)}
            />
          )}
          {state.status === "finished" && (
            <View style={styles.panel}>
              <Text style={styles.title}>
                우승:{" "}
                {state.winners
                  .map((s) => state.players.find((p) => p.seat === s)?.name)
                  .join(", ")}
              </Text>
            </View>
          )}
          {turn && player && player.hp <= 0 && !movementHold && (
            <View style={styles.panel}>
              <Text style={[styles.text, { marginBottom: 12 }]}>
                기절하여 이번 턴은 쉬어야 해요. 다음 자기 턴에 이 자리에서
                부활해요.
              </Text>
              <Button
                label="쉬는 턴 마치기"
                disabled={locked}
                onPress={() => void act("end_turn")}
              />
            </View>
          )}
          {turn &&
            player &&
            player.hp > 0 &&
            state.hand_task &&
            !movementHold && (
              <View style={styles.panel}>
                <Text style={[styles.text, { marginBottom: 12 }]}>
                  {state.hand_task.reason} · 손패를 모두 버리고{" "}
                  {state.hand_task.count !== null
                    ? `${state.hand_task.count}장`
                    : "캐릭터의 최대 손패"}
                  까지 새로 획득해주세요.
                  {state.hand_task.reason === "부활"
                    ? " 패시브도 초기화되었어요."
                    : ""}
                </Text>
                <Button
                  label="손패 교체 완료"
                  disabled={locked}
                  onPress={() =>
                    void act("ack_hand", {
                      task_version: state.hand_task!.version,
                    })
                  }
                />
              </View>
            )}
          {turn && state.counter_prompt && !counter && (
            <Text style={styles.text}>상대가 반격 여부를 선택하고 있어요.</Text>
          )}
          {canMove && player && tile && !showDuel && (
            <View style={{ marginBottom: 12, gap: 12 }}>
              {!!state.item_reward && (
                <View style={{ marginBottom: 12 }}>
                  <Text style={styles.text}>
                    {state.board.shop[state.item_reward]!.label} 획득! 교체할
                    아이템을 선택해주세요.
                  </Text>
                  {state.me!.items.map((item, index) => (
                    <Button
                      key={index}
                      label={`${state.board.shop[item]!.label} 교체`}
                      disabled={locked}
                      onPress={() => void act("claim_item", { index })}
                    />
                  ))}
                  <Button
                    label="새 아이템 받지 않기"
                    disabled={locked}
                    onPress={() => void act("claim_item", { discard: true })}
                  />
                </View>
              )}
              {state.move ? (
                <>
                  <Text style={styles.text}>
                    남은 이동 {state.move.remaining}칸
                  </Text>
                  {state.move_prompt ? (
                    <View style={{ marginTop: 12 }}>
                      {!!state.move_prompt.targets.length && (
                        <Text style={styles.text}>
                          상대를 지나치는 중입니다. 교전하거나 계속 이동할 수
                          있어요.
                        </Text>
                      )}
                      <Button
                        label={
                          state.move_prompt.shop_open
                            ? "상점 닫고 계속 이동"
                            : "계속 이동"
                        }
                        disabled={locked}
                        onPress={() => void act("continue_move")}
                      />
                    </View>
                  ) : (
                    <Text style={[styles.muted, { marginTop: 12 }]}>
                      {forward.length > 1
                        ? "지도 화살표를 눌러 방향을 선택하세요."
                        : "진행 방향으로 이동 중…"}
                    </Text>
                  )}
                </>
              ) : null}
              {(state.landed ||
                state.move_prompt ||
                state.arrival === "dash") && (
                <>
                  {!!duelTargets.length && (
                    <Button
                      label="전투"
                      disabled={locked}
                      onPress={() => setReleasedEncounter("")}
                    />
                  )}
                  {state.landed &&
                    !state.can_transfer &&
                    !state.can_auto_end_turn &&
                    !state.can_buy_item &&
                    !state.can_charge &&
                    !state.camp_gift &&
                    !state.item_reward && (
                      <View style={{ marginTop: 16 }}>
                        <Button
                          label="턴 종료"
                          disabled={locked}
                          onPress={() => void act("end_turn")}
                        />
                      </View>
                    )}
                </>
              )}
            </View>
          )}
          {state.battle && (
            <View style={styles.panel}>
              <Text style={styles.title}>
                {battlePlayers.map((p) => p.name).join(" ↔ ")}
              </Text>
              <Text style={[styles.text, { marginBottom: 12 }]}>
                {state.battle.completed && state.battle.exchanges === 1
                  ? "첫 공방 기절 · 전투 종료"
                  : `공방 ${state.battle.exchanges}/2`}{" "}
                · {battlePlayers.map((p) => `♥${p.hp}`).join(" / ")}
              </Text>
              <Button
                label={
                  state.battle.control_token
                    ? "교전 계산기로 이동"
                    : "계산기 관전"
                }
                disabled={locked}
                onPress={() => void openCalculator(state)}
              />
              {state.battle.can_confirm && (
                <View style={{ marginTop: 16 }}>
                  <Text style={[styles.muted, { marginBottom: 10 }]}>
                    참가자 한 명이 제출하면 HP와 기절 결과가 바로 반영됩니다.
                  </Text>
                  <Button
                    label="전투 결과 반영"
                    disabled={locked}
                    onPress={() =>
                      void act("confirm_battle", {
                        battle_version: state.battle!.version,
                      })
                    }
                  />
                </View>
              )}
              {state.me?.is_host && (
                <View style={{ marginTop: 16 }}>
                  <Button
                    label="교전 취소"
                    danger
                    disabled={locked}
                    onPress={() => void act("cancel_battle")}
                  />
                </View>
              )}
            </View>
          )}
          <PartySupplyChoice
            crate={state.supply_encounter}
            visible={
              turn &&
              !movementHold &&
              !showDuel &&
              !state.battle &&
              !state.hand_task &&
              !state.item_reward &&
              !state.camp_gift &&
              !eventStage
            }
            visit={`${state.code}:${state.me?.seat}:${state.turn_number}:${state.move_path?.version}`}
            locked={locked}
            onAttack={(combo) =>
              void act("attack_supply", {
                crate_id: state.supply_encounter?.id,
                ...combo,
              })
            }
            onSkip={() =>
              void act("skip_supply", { crate_id: state.supply_encounter?.id })
            }
          />
          <PartyCardPreview
            card={cardPreview ? state.board.shop[cardPreview] || null : null}
            onClose={() => setCardPreview(null)}
          />
          <View style={styles.panel}>
            <Text style={styles.title}>테이블 기록</Text>
            {visibleState!.log
              .slice(-15)
              .reverse()
              .map((entry, index) => (
                <Text key={index} style={[styles.muted, { marginBottom: 8 }]}>
                  {entry.text}
                </Text>
              ))}
          </View>
        </>
      )}
    </ScrollView>
  );
}

function PartyMap({
  state,
  selected,
  onSelect,
  routeTarget,
  itemTargets,
  itemTarget,
  onDirectionSelect,
  onMovementComplete,
  cameraRequest,
  canMove,
  interactionSeq,
}: {
  state: PartyState;
  selected?: number;
  onSelect: (node: PartyTile) => void;
  routeTarget: number | null;
  itemTargets: number[];
  itemTarget?: number;
  onDirectionSelect: (id: number) => void;
  onMovementComplete: (version: number) => void;
  cameraRequest: { seat: number; id: number } | null;
  canMove: boolean;
  interactionSeq: number;
}) {
  return (
    <PartyBoard3D
      state={state}
      selected={selected}
      onSelect={onSelect}
      routeTarget={routeTarget}
      itemTargets={itemTargets}
      itemTarget={itemTarget}
      onDirectionSelect={onDirectionSelect}
      onMovementComplete={onMovementComplete}
      cameraRequest={cameraRequest}
      canMove={canMove}
      interactionSeq={interactionSeq}
      fallback={
        <PartyMap2D
          state={state}
          selected={selected}
          onSelect={onSelect}
          routeTarget={routeTarget}
          itemTargets={itemTargets}
          itemTarget={itemTarget}
          onDirectionSelect={onDirectionSelect}
          canMove={canMove}
        />
      }
    />
  );
}

function PartyMap2D({
  state,
  selected,
  onSelect,
  routeTarget,
  itemTargets,
  itemTarget,
  onDirectionSelect,
  canMove,
}: {
  state: PartyState;
  selected?: number;
  onSelect: (node: PartyTile) => void;
  routeTarget: number | null;
  itemTargets: number[];
  itemTarget?: number;
  onDirectionSelect: (id: number) => void;
  canMove: boolean;
}) {
  const [size, setSize] = useState(300);
  const mine = state.players.find((p) => p.seat === state.me?.seat);
  const exits =
    canMove &&
    mine &&
    state.turn === mine.seat &&
    state.move &&
    !state.move_prompt &&
    !state.battle
      ? (mine.forward_exits ?? state.board.nodes[mine.position]!.exits)
      : [];
  const bounds = state.board.bounds || { min: 0, max: 100 };
  const normalize = (value: number) =>
    ((value - bounds.min) * 100) / (bounds.max - bounds.min);
  const mapNodes = state.board.nodes.map((tile) => ({
    ...tile,
    x: normalize(tile.x),
    y: normalize(tile.y),
  }));
  const tileSize = (state.board.version || 1) >= 2 ? 0.046 : 0.075;
  const lines: React.ReactNode[] = [];
  const preview = state.movement_preview;
  const focused = preview?.routes[String(routeTarget)];
  const routeNodes = new Set(preview?.nodes || []);
  const routeEdges = new Set(preview?.edges || []);
  const focusedNodes = new Set(focused?.nodes || []);
  const focusedEdges = new Set(focused?.edges || []);
  const drawn = new Set<string>();
  mapNodes.forEach((tile) =>
    tile.exits.forEach((id) => {
      const key = [tile.id, id].sort((a, b) => a - b).join("-");
      if (drawn.has(key)) return;
      drawn.add(key);
      const other = mapNodes[id]!,
        dx = ((other.x - tile.x) * size) / 100,
        dy = ((other.y - tile.y) * size) / 100;
      const length = Math.hypot(dx, dy);
      lines.push(
        <View
          key={key}
          pointerEvents="none"
          style={{
            position: "absolute",
            height: routeEdges.has(key) ? 2.2 : 0.6,
            width: length,
            backgroundColor: routeEdges.has(key) ? "#86ffd1" : colors.line,
            opacity:
              routeEdges.has(key) && focused && !focusedEdges.has(key)
                ? 0.16
                : 1,
            left: ((tile.x + other.x) * size) / 200 - length / 2,
            top: ((tile.y + other.y) * size) / 200,
            transform: [
              { rotate: `${(Math.atan2(dy, dx) * 180) / Math.PI}deg` },
            ],
          }}
        />,
      );
    }),
  );
  const choices =
    mine && exits.length > 1
      ? exits.map((id) => {
          const from = mapNodes[mine.position]!,
            other = mapNodes[id]!;
          const dx = other.x - from.x,
            dy = other.y - from.y,
            length = Math.hypot(dx, dy);
          const lane = other.exits.includes(from.id) ? 0.6 : 0;
          const x = from.x + dx * 0.55 - (dy / length) * lane;
          const y = from.y + dy * 0.55 + (dx / length) * lane;
          const label =
            other.ring === from.ring
              ? id === (from.clockwise ?? from.exits[0])
                ? "시계 방향"
                : "반시계 방향"
              : other.ring === "inner"
                ? "중앙 길"
                : "외곽 길";
          return (
            <Pressable
              key={`choice-${id}`}
              accessibilityRole="button"
              accessibilityLabel={`방향 선택 · ${label}`}
              onPress={() => onDirectionSelect(id)}
              style={[
                mapStyles.choice,
                { left: (x * size) / 100 - 22, top: (y * size) / 100 - 22 },
              ]}
            >
              <Text
                style={{
                  fontSize: 28,
                  lineHeight: 32,
                  color: "#164b43",
                  transform: [
                    { rotate: `${(Math.atan2(dy, dx) * 180) / Math.PI}deg` },
                  ],
                }}
              >
                ➜
              </Text>
            </Pressable>
          );
        })
      : [];
  return (
    <View
      onLayout={(e) => setSize(e.nativeEvent.layout.width)}
      style={{ height: size, width: "100%" }}
    >
      {lines}
      <Text
        style={{
          position: "absolute",
          top: size / 2 - 8,
          left: size / 2 - 22,
          color: colors.muted,
          fontSize: 10,
        }}
      >
        LUMEN
      </Text>
      {mapNodes.map((tile) => (
        <Pressable
          key={tile.id}
          accessibilityRole="button"
          accessibilityLabel={tile.label}
          onPress={() => onSelect(tile)}
          style={[
            mapStyles.tile,
            {
              width: size * tileSize,
              height: size * tileSize,
              left: (tile.x * size) / 100 - (size * tileSize) / 2,
              top: (tile.y * size) / 100 - (size * tileSize) / 2,
              borderColor: itemTargets.includes(tile.id)
                ? itemTarget === tile.id
                  ? "#fff"
                  : "#ffb465"
                : routeTarget === tile.id
                  ? "#ffe094"
                  : routeNodes.has(tile.id)
                    ? focused && !focusedNodes.has(tile.id)
                      ? "#86ffd132"
                      : "#86ffd1"
                    : selected === tile.id
                      ? colors.accent
                      : colors.line,
              borderWidth:
                routeNodes.has(tile.id) || itemTargets.includes(tile.id)
                  ? 3
                  : 1,
              backgroundColor:
                (
                  {
                    camp: "#bd9449",
                    dash: "#214437",
                    charge: "#442b3a",
                    shop: "#503a28",
                    prepare: "#39304e",
                    disaster: "#4b2c2b",
                    fortune: "#214148",
                    event: "#42304d",
                  } as Record<string, string>
                )[tile.kind] || colors.panel,
            },
          ]}
        >
          <Text style={{ fontSize: 12, color: colors.text }}>{tile.icon}</Text>
          {!!tile.background_img && (
            <TileImage
              source={{ uri: absoluteUrl(tile.background_img) }}
              contentFit="contain"
              style={{
                position: "absolute",
                width: "100%",
                height: "100%",
                left: 0,
                top: 0,
              }}
            />
          )}
          {tile.kind === "camp" &&
            state.players
              .filter((p) => p.home === tile.id)
              .map((p) => (
                <Image
                  key={`home-${p.seat}`}
                  source={{
                    uri: absoluteUrl(p.character.icon_img || p.character.img),
                  }}
                  accessibilityLabel={`${p.name}의 거점`}
                  resizeMode="contain"
                  style={{
                    position: "absolute",
                    width: "70%",
                    height: "70%",
                    left: "15%",
                    top: "15%",
                    opacity: 0.4,
                    transform: [{ rotate: "45deg" }],
                  }}
                />
              ))}
          <View style={mapStyles.pawns}>
            {state.players
              .filter((p) => p.position === tile.id)
              .map((p) => (
                <View
                  key={p.seat}
                  style={{
                    width: 30,
                    height: 45,
                    opacity: p.cloaked ? 0.35 : p.hp <= 0 ? 0.45 : 1,
                  }}
                >
                  {!!(
                    p.character.body_img ||
                    p.character.sd_img ||
                    p.character.icon_img ||
                    p.character.img
                  ) && (
                    <Image
                      source={{
                        uri: absoluteUrl(
                          p.character.body_img ||
                            p.character.sd_img ||
                            p.character.icon_img ||
                            p.character.img,
                        ),
                      }}
                      accessibilityLabel={`${p.name} · ${p.character.name}`}
                      resizeMode="contain"
                      style={{ width: 30, height: 45 }}
                    />
                  )}
                  <Text
                    style={{
                      position: "absolute",
                      bottom: -3,
                      right: -2,
                      width: 14,
                      height: 14,
                      borderRadius: 7,
                      textAlign: "center",
                      fontSize: 9,
                      fontWeight: "800",
                      backgroundColor: pawnColors[p.seat],
                      color: "#15223b",
                    }}
                  >
                    {p.seat + 1}
                  </Text>
                </View>
              ))}
          </View>
          {state.roadblocks?.some((b) => b.node === tile.id) && (
            <Text
              accessibilityLabel="통행 금지"
              style={{
                position: "absolute",
                right: -5,
                top: -8,
                color: "#ff5269",
                fontSize: 18,
                fontWeight: "900",
              }}
            >
              ▰
            </Text>
          )}
          {state.supplies?.some((crate) => crate.node === tile.id) && (
            <Text
              accessibilityLabel={`보급함 HP ${state.supplies.find((crate) => crate.node === tile.id)?.hp}`}
              style={{
                position: "absolute",
                right: -8,
                top: -12,
                color: "#ffce78",
                fontSize: 24,
                fontWeight: "900",
              }}
            >
              ▣
            </Text>
          )}
        </Pressable>
      ))}
      {choices}
    </View>
  );
}
const mapStyles = StyleSheet.create({
  choice: {
    position: "absolute",
    width: 44,
    height: 44,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#8bffcf",
    borderWidth: 2,
    borderColor: "#effff8",
    zIndex: 10,
  },
  tile: {
    position: "absolute",
    borderRadius: 5,
    alignItems: "center",
    justifyContent: "center",
  },
  pawns: { position: "absolute", bottom: 8, flexDirection: "row", gap: 2 },
});
