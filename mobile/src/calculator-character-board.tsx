import React, { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Animated,
  AppState,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { CalculatorBoard, type CalculatorBoardProps } from "./calculator-board";
import { calculatorTheme } from "./calculator-ui";
import { localized } from "./core";
import { PassiveTray } from "./calculator-passive-tray-view";
import { hpAppearance } from "./calculator-display";
import { prefersShieldRow, shieldAmount, supportsShield } from "./calculator-shield";
import { hpBar, hpButtonRows, HP_STEPS_4, HP_STEPS_8 } from "./calculator-layout";
import { useApp } from "./provider";
import { CachedImage } from "./ui";
import { CharacterIconImage } from "./character-picker";
import type { Action, Player } from "./types";
import { setCalculatorAppearance, useCalculatorAppearance } from "./calculator-appearance-settings";
import type { CalculatorAppearance } from "./calculator-appearance";

export default function CharacterCalculatorBoard(props: CalculatorBoardProps) {
  const { catalog, language } = useApp();
  const display = useCalculatorAppearance();
  const [reduced, setReduced] = useState(true);
  const [foreground, setForeground] = useState(
    AppState.currentState === "active",
  );
  const quietUntil = useRef(0);
  const intentUntil = useRef(0);
  const connection = useRef(props.connected);
  if (connection.current !== props.connected) {
    quietUntil.current = Date.now() + 1200;
    connection.current = props.connected;
  }
  useEffect(() => {
    let live = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((value) => {
        if (live) setReduced(value);
      })
      .catch(() => undefined);
    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      setReduced,
    );
    const appSubscription = AppState.addEventListener("change", (state) =>
      setForeground(state === "active"),
    );
    return () => {
      live = false;
      subscription.remove();
      appSubscription.remove();
    };
  }, []);
  const action = (value: Action) => {
    intentUntil.current = Date.now() + 5000;
    if (["undo", "reset_session", "sudden_death"].includes(value.action))
      quietUntil.current = Date.now() + 1500;
    return props.onAction(value);
  };
  return (
    <>
    <HpButtonChooser visible={!!props.state && !props.disabled && display.hpButtons === null} />
    <CalculatorBoard
      {...props}
      onAction={action}
      appearance="character"
      setup={props.setup}
      renderPlayer={(target, onDamage) => {
        const stored = props.state?.players[target];
        if (!stored) return null;
        const entry =
          props.mode === "local"
            ? catalog?.characters.find((c) => c.id === stored.character?.id)
            : undefined;
        const player: Player = entry
          ? {
              ...stored,
              name: localized(entry, language),
              character: {
                ...stored.character,
                name: localized(entry, language),
                color: entry.color,
                calculator_ui: entry.calculator_ui,
                passive: localized(entry, language, "passive"),
                hand_table: entry.hand_table,
                img_sm: entry.img_sm,
                trait_img:
                  entry.traits?.find((trait) => trait.id === stored.character?.trait_card_id)?.img ||
                  entry.traits?.[0]?.img,
              },
            }
          : stored;
        return (
          <CharacterPlayer
            key={target}
            player={player}
            target={target}
            display={display}
            disabled={props.disabled}
            pendingHp={props.pendingHp[target]}
            pendingFp={props.pendingFp[target]}
            pendingShield={props.pendingShield[target]}
            onShield={amount => props.onShield(target, amount)}
            onHp={(amount, immediate) => {
              intentUntil.current = Date.now() + 5000;
              props.onHp(target, amount, immediate);
            }}
            onFp={(amount) => {
              intentUntil.current = Date.now() + 5000;
              props.onFp(target, amount);
            }}
            onDamage={onDamage}
            onAction={action}
            ambientAllowed={!reduced && foreground}
            motionAllowed={() =>
              !reduced &&
              Date.now() > quietUntil.current &&
              Date.now() < intentUntil.current &&
              (props.mode !== "shared" || props.connected)
            }
          />
        );
      }}
    />
    </>
  );
}

/** 처음 접속한 조작자에게 HP 버튼 방식을 한 번 묻는다. 고른 값은 기기에 저장되어 다시 묻지 않는다. */
function HpButtonChooser({ visible }: { visible: boolean }) {
  const { t } = useApp();
  const preview = (rows: number[][]) => (
    <View style={{ gap: 4 }}>
      {rows.map((row, i) => (
        <View key={i} style={{ flexDirection: "row", gap: 3 }}>
          {row.map((value) => (
            <Text
              key={value}
              style={[s.chooseCell, value < 0 ? { color: C.damage, backgroundColor: "rgba(255,111,111,0.14)" } : { color: C.heal, backgroundColor: "rgba(69,208,160,0.12)" }]}
            >
              {value > 0 ? "+" : "−"}
              {Math.abs(value)}
            </Text>
          ))}
        </View>
      ))}
    </View>
  );
  return (
    <Modal visible={visible} transparent animationType="fade" supportedOrientations={["portrait", "landscape", "landscape-left", "landscape-right"]}>
      <View style={s.chooseBackdrop}>
        <View style={s.chooseSheet}>
          <Text accessibilityRole="header" style={s.chooseTitle}>
            {t("HP 버튼 방식")}
          </Text>
          <Text style={s.chooseNote}>{t("처음 한 번만 묻습니다. 나중에 계산기 설정에서 바꿀 수 있습니다.")}</Text>
          <View style={{ flexDirection: "row", gap: 8 }}>
            {(
              [
                ["4", t("4버튼"), [HP_STEPS_4]],
                ["8", t("8버튼"), [HP_STEPS_8.slice(0, 4), HP_STEPS_8.slice(4)]],
              ] as const
            ).map(([mode, label, rows]) => (
              <Pressable
                key={mode}
                accessibilityRole="button"
                accessibilityLabel={label}
                onPress={() => setCalculatorAppearance({ hpButtons: mode })}
                style={({ pressed }) => [s.chooseOption, pressed && { borderColor: C.gold }]}
              >
                <Text style={s.chooseLabel}>{label}</Text>
                {preview(rows as unknown as number[][])}
              </Pressable>
            ))}
          </View>
          <Text style={s.chooseNote}>{t("4버튼은 두 번째 줄에 보호막 버튼이 들어갑니다. 보호막 특성(핀프 등)은 8버튼이어도 4버튼 + 보호막 줄입니다.")}</Text>
        </View>
      </View>
    </Modal>
  );
}

type PlayerProps = {
  display: CalculatorAppearance;
  player: Player;
  target: "p1" | "p2";
  disabled: boolean;
  pendingHp: number;
  pendingFp: number;
  pendingShield: number;
  onShield: (amount: number) => void;
  onHp: (amount: number, immediate?: boolean) => void;
  onFp: (amount: number) => void;
  onDamage: () => void;
  onAction: (action: Action) => Promise<void>;
  motionAllowed: () => boolean;
  ambientAllowed: boolean;
};
const C = {
  panel: "#131823",
  text: "#f2f0ea",
  muted: "#9ba4b4",
  line: "rgba(255,255,255,0.09)",
  damage: "#ff6f6f",
  heal: "#45d0a0",
  fp: "#b892ff",
  gold: "#e8bd62",
};
/**
 * 웹 calculator.css의 .lc-player와 같은 구성. P1은 [HP | FP], P2는 [FP | HP]로
 * 가운데를 기준으로 대칭이고, FP는 HP 옆 세로 열(+ / 값 / −)이다. 패시브는 스크롤 없이 맞춘다.
 */
function CharacterPlayer({
  player,
  target,
  disabled,
  pendingHp,
  pendingFp,
  pendingShield,
  onShield,
  onHp,
  onFp,
  onDamage,
  onAction,
  motionAllowed,
  display,
}: PlayerProps) {
  const { t } = useApp();
  const { width, height } = useWindowDimensions();
  // 세로 화면에서는 패널 높이가 화면의 절반 남짓이라 작은 크기로 그린다.
  const compact = height < 500 || height > width;
  const mirrored = target === "p2";
  const theme = calculatorTheme(player.character);
  const health = hpAppearance(player.hp, player.initial_hp);
  const label = t(target === "p1" ? "플레이어1" : "플레이어2");
  const table = player.character?.hand_table || {};
  const thresholds = Object.keys(table)
    .map(Number)
    .sort((a, b) => a - b);
  const threshold = thresholds.find((n) => player.hp <= n) ?? thresholds.at(-1);
  const hand = threshold === undefined ? "—" : table[threshold];
  const characterName = String(player.character?.name || "");
  const avatar = String(player.character?.icon_img || player.character?.img_sm || "");
  const shield = shieldAmount(player);
  const illustrated = display.style === "illustrated";
  const pulse = useRef(new Animated.Value(0)).current;
  const snapshot = JSON.stringify([player.character?.id, player.hp, player.fp, player.passive_state]);
  const previous = useRef({ snapshot, character: player.character?.id });
  useEffect(() => {
    const before = previous.current;
    previous.current = { snapshot, character: player.character?.id };
    if (before.snapshot === snapshot || before.character !== player.character?.id || !illustrated || !motionAllowed())
      return;
    pulse.stopAnimation();
    pulse.setValue(0.6);
    Animated.timing(pulse, { toValue: 0, duration: 420, useNativeDriver: true }).start();
  }, [snapshot]);
  const bar = hpBar(player.hp, player.initial_hp, shield);
  const low = bar.ratio <= 0.3;
  // HP 조작부는 항상 두 줄(4×2 기준) 높이. 4버튼이면 두 번째 줄이 보호막(모든 캐릭터 공통)이고,
  // 보호막 특성(핀프 등)은 8버튼 설정이어도 4버튼 + 보호막 줄이다.
  const rows = hpButtonRows(display.hpButtons, prefersShieldRow(player), mirrored);
  const hasShield = rows.length === 1 && supportsShield(player);
  // 패시브 칸은 패널 높이의 28%(96~150)까지만, 나머지 높이는 HP·FP 조작부가 쓴다.
  const [panelHeight, setPanelHeight] = useState(0);
  // 태블릿처럼 큰 화면은 HP·FP 조작부가 충분히 크므로 패시브 칸을 2배 넘게(최대 340) 키운다.
  const large = !compact && width >= 768 && height >= 600;
  const passiveMax = large
    ? Math.round(Math.max(200, Math.min(340, panelHeight * 0.44)))
    : Math.round(Math.max(96, Math.min(150, panelHeight * 0.28)));
  return (
    <View
      onLayout={(e) => setPanelHeight(e.nativeEvent.layout.height)}
      style={[
        s.player,
        { borderColor: low ? C.damage + "88" : theme.accent + "55", padding: compact ? 7 : 12, gap: compact ? 6 : 10 },
      ]}
    >
      <View
        pointerEvents="none"
        style={StyleSheet.absoluteFill}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        <View style={[StyleSheet.absoluteFill, { backgroundColor: theme.accent, opacity: 0.1 }]} />
        {illustrated && !!player.character?.img && (
          <View style={[s.portrait, mirrored && { left: "-10%", right: undefined }, { opacity: 0.3 + 0.7 * (display.brightness / 100) }]}>
            <CachedImage
              key={String(player.character.id) + ":" + player.character.img}
              url={player.character.img}
              fill
              transparent
              height="100%"
              contentPosition={mirrored ? "left center" : "right center"}
            />
          </View>
        )}
        {illustrated && <View style={[StyleSheet.absoluteFill, { backgroundColor: "#0b0e14", opacity: 0.45 }]} />}
      </View>
      <View style={[s.controls, mirrored && { flexDirection: "row-reverse" }]}>
        <View style={s.main}>
          <View style={[s.head, mirrored && { flexDirection: "row-reverse" }]}>
            {!!avatar && (
              <View style={[s.avatar, compact && { width: 26, height: 26 }, { borderColor: theme.accent }]}>
                <CharacterIconImage url={avatar} width={compact ? 26 : 30} height={compact ? 26 : 30} circle />
              </View>
            )}
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text numberOfLines={1} maxFontSizeMultiplier={1.2} style={[s.name, mirrored && { textAlign: "right" }]}>
                {player.name}
              </Text>
              {!!characterName && characterName !== player.name && (
                <Text numberOfLines={1} maxFontSizeMultiplier={1.2} style={[s.character, { color: theme.secondary }, mirrored && { textAlign: "right" }]}>
                  {characterName}
                </Text>
              )}
            </View>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${label} HP ${player.hp}${shield ? `, ${t("보호막")} ${shield}` : ""}, ${t("대미지 적용")}`}
              disabled={disabled}
              onPress={onDamage}
              style={[s.hp, mirrored && { flexDirection: "row-reverse" }]}
            >
              <Text maxFontSizeMultiplier={1} style={[s.hpValue, { color: player.hp <= 0 ? "#687183" : health.strong, fontSize: compact ? 26 : 40 }]}>
                {player.hp}
              </Text>
              {!!shield && <Text style={[s.shieldValue, { fontSize: compact ? 13 : 17 }]}>+{shield}</Text>}
              {!!pendingHp && (
                <Text
                  accessibilityLabel={`${label} ${t("누적 HP 변화")} ${pendingHp}`}
                  style={[
                    s.pending,
                    mirrored ? { left: 0 } : { right: 0 },
                    pendingHp < 0
                      ? { color: C.damage, backgroundColor: "rgba(40,14,14,0.92)", borderColor: C.damage }
                      : { color: C.heal, backgroundColor: "rgba(10,32,26,0.92)", borderColor: C.heal },
                  ]}
                >
                  {pendingHp > 0 ? "+" : "−"}
                  {Math.abs(pendingHp)}
                </Text>
              )}
            </Pressable>
            <Text maxFontSizeMultiplier={1.2} style={s.hand}>
              {t("손패")} {hand}
            </Text>
          </View>
          <View style={[s.barTrack, mirrored && { flexDirection: "row-reverse" }]} pointerEvents="none">
            <View style={{ width: `${bar.hp * 100}%`, backgroundColor: health.strong }} />
            <View style={{ width: `${bar.shield * 100}%`, backgroundColor: "#5aa8f0" }} />
          </View>
          {rows.map((row, i) => (
            <View key={i} style={s.hpButtons}>
              {row.map((amount) => (
                <Pressable
                  key={amount}
                  accessibilityRole="button"
                  accessibilityLabel={`${label} HP ${amount > 0 ? "+" : ""}${amount}`}
                  accessibilityState={{ disabled }}
                  disabled={disabled}
                  onPress={() => onHp(amount, rows.length > 1)}
                  style={({ pressed }) => [
                    s.hpButton,
                    amount < 0
                      ? { borderColor: "rgba(255,111,111,0.32)", backgroundColor: Math.abs(amount) >= 500 ? "#3a1c22" : "#2a181d" }
                      : { borderColor: "rgba(69,208,160,0.3)", backgroundColor: Math.abs(amount) >= 500 ? "#123229" : "#11241f" },
                    disabled && { opacity: 0.4 },
                    pressed && { transform: [{ scale: 0.96 }] },
                  ]}
                >
                  <Text
                    adjustsFontSizeToFit
                    numberOfLines={1}
                    maxFontSizeMultiplier={1.2}
                    style={[s.hpStep, { color: amount < 0 ? C.damage : C.heal, fontSize: compact ? 15 : 20 }]}
                  >
                    {amount > 0 ? "+" : "−"}
                    {Math.abs(amount)}
                  </Text>
                </Pressable>
              ))}
            </View>
          ))}
          {hasShield && (
            <View style={s.shieldRow}>
              {[-100, 0, 100].map((step) => (
                <Pressable
                  key={step}
                  accessibilityRole="button"
                  accessibilityLabel={`${label} ${t("보호막")} ${step ? (step > 0 ? "+100" : "-100") : t("초기화")}`}
                  accessibilityState={{ disabled }}
                  disabled={disabled}
                  onPress={() => (step ? onShield(step) : void onAction({ action: "shield_reset", target }))}
                  style={({ pressed }) => [s.shieldButton, disabled && { opacity: 0.4 }, pressed && { transform: [{ scale: 0.96 }] }]}
                >
                  {/* 보호막 줄은 파란 버튼 셋으로 −100 · RESET · +100만 적는다. */}
                  <Text adjustsFontSizeToFit numberOfLines={2} maxFontSizeMultiplier={1.2} style={[s.shieldText, { fontSize: compact ? 15 : 20 }]}>
                    {step ? (step > 0 ? "+100" : "−100") : "RESET"}
                    {!!step && pendingShield * step > 0 ? `\n${pendingShield > 0 ? "+" : "−"}${Math.abs(pendingShield)}` : ""}
                  </Text>
                </Pressable>
              ))}
            </View>
          )}
        </View>
        <View style={[s.fp, { width: compact ? 54 : 76 }]}>
          <Step label={`${label} FP +1`} text={pendingFp > 0 ? `+${pendingFp}` : "+"} disabled={disabled} compact={compact} onPress={() => onFp(1)} />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${label} FP ${player.fp}, ${t("초기화")}`}
            disabled={disabled}
            onPress={() => onAction({ action: "fp_reset", target })}
            style={s.fpValue}
          >
            <Text style={s.caption}>FP</Text>
            <Text
              adjustsFontSizeToFit
              numberOfLines={1}
              maxFontSizeMultiplier={1}
              style={[s.fpNumber, { fontSize: compact ? 20 : 30, color: player.fp > 0 ? C.fp : player.fp < 0 ? C.damage : C.muted }]}
            >
              {player.fp > 0 ? "+" + player.fp : player.fp}
            </Text>
          </Pressable>
          <Step label={`${label} FP -1`} text={pendingFp < 0 ? `−${Math.abs(pendingFp)}` : "−"} disabled={disabled} compact={compact} onPress={() => onFp(-1)} />
        </View>
      </View>
      <PassiveTray
        player={player}
        target={target}
        definition={player.character?.passive || {}}
        disabled={disabled}
        accent={theme.accent}
        maxHeight={passiveMax}
        large={large}
        onAction={(value) => void onAction(value)}
      />
      <Animated.View
        pointerEvents="none"
        style={[StyleSheet.absoluteFill, { borderWidth: 2, borderRadius: 18, borderColor: theme.accent, opacity: pulse }]}
      />
    </View>
  );
}
function Step({ label, text, disabled, compact, onPress }: { label: string; text: string; disabled: boolean; compact: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [s.step, { flex: 1, minHeight: compact ? 34 : 44 }, disabled && { opacity: 0.4 }, pressed && { transform: [{ scale: 0.96 }] }]}
    >
      <Text adjustsFontSizeToFit numberOfLines={1} maxFontSizeMultiplier={1.2} style={[s.stepText, { fontSize: compact ? 22 : 30 }]}>
        {text}
      </Text>
    </Pressable>
  );
}
const s = StyleSheet.create({
  player: {
    flex: 1,
    minWidth: 0,
    borderWidth: 1,
    borderRadius: 18,
    overflow: "hidden",
    backgroundColor: C.panel,
  },
  portrait: { position: "absolute", right: "-10%", top: 0, bottom: "-3%", width: "90%" },
  head: { flexDirection: "row", alignItems: "center", gap: 8 },
  avatar: { width: 30, height: 30, borderRadius: 15, borderWidth: 2, overflow: "hidden" },
  name: { color: C.text, fontSize: 15, fontWeight: "800" },
  character: { fontSize: 11, opacity: 0.85 },
  hand: {
    color: C.gold,
    fontSize: 12,
    fontWeight: "800",
    paddingVertical: 3,
    paddingHorizontal: 9,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(232,189,98,0.45)",
    backgroundColor: "rgba(232,189,98,0.1)",
    overflow: "hidden",
  },
  controls: { flex: 1, minHeight: 0, flexDirection: "row", gap: 8 },
  main: { flex: 1, minWidth: 0, minHeight: 0, gap: 6 },
  caption: { color: C.muted, fontSize: 10, fontWeight: "800", letterSpacing: 1.2 },
  hp: { flexDirection: "row", alignItems: "baseline", gap: 3 },
  hpValue: { fontWeight: "900", letterSpacing: -1, fontVariant: ["tabular-nums"] },
  shieldValue: { color: "#8cc8ff", fontWeight: "800" },
  barTrack: { height: 8, borderRadius: 4, backgroundColor: "rgba(255,255,255,0.08)", overflow: "hidden", flexDirection: "row" },
  pending: {
    position: "absolute",
    top: "100%",
    marginTop: 4,
    zIndex: 2,
    paddingVertical: 1,
    paddingHorizontal: 7,
    borderRadius: 7,
    borderWidth: 1,
    borderStyle: "dashed",
    fontWeight: "900",
    fontSize: 13,
    overflow: "hidden",
  },
  fp: { gap: 6 },
  fpValue: {
    minHeight: 44,
    paddingVertical: 4,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(184,146,255,0.3)",
    backgroundColor: "rgba(5,7,11,0.62)",
  },
  fpNumber: { fontWeight: "900", fontVariant: ["tabular-nums"] },
  step: {
    borderRadius: 12,
    borderWidth: 1,
    borderColor: C.line,
    backgroundColor: "rgba(9,12,18,0.82)",
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { color: C.fp, fontWeight: "800" },
  hpButtons: { flex: 1, minHeight: 34, flexDirection: "row", gap: 6 },
  hpButton: { flex: 1, minWidth: 0, borderWidth: 1, borderRadius: 12, alignItems: "center", justifyContent: "center", paddingHorizontal: 2 },
  hpStep: { fontWeight: "900", fontVariant: ["tabular-nums"] },
  shieldRow: { flex: 1, minHeight: 34, flexDirection: "row", gap: 6 },
  shieldButton: {
    flex: 1,
    minWidth: 0,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(120,190,255,0.32)",
    backgroundColor: "rgba(40,90,140,0.22)",
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  shieldText: { color: "#a9d6ff", fontSize: 15, fontWeight: "900", textAlign: "center" },
  chooseBackdrop: { flex: 1, backgroundColor: "rgba(2,4,8,0.65)", alignItems: "center", justifyContent: "center", padding: 16 },
  chooseSheet: { width: 420, maxWidth: "100%", gap: 10, padding: 16, borderRadius: 18, borderWidth: 1, borderColor: "rgba(255,255,255,0.18)", backgroundColor: "#121722" },
  chooseTitle: { color: C.text, fontSize: 18, fontWeight: "800" },
  chooseNote: { color: C.muted, fontSize: 12 },
  chooseOption: { flex: 1, gap: 8, padding: 10, borderRadius: 12, borderWidth: 1, borderColor: "rgba(255,255,255,0.18)", backgroundColor: "rgba(9,12,18,0.6)" },
  chooseLabel: { color: C.text, fontSize: 15, fontWeight: "800" },
  chooseCell: { flex: 1, textAlign: "center", fontSize: 10.5, fontWeight: "800", paddingVertical: 4, borderRadius: 6, overflow: "hidden" },
});
