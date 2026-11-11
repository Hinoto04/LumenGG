import React, { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Animated,
  AppState,
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
import { shieldAmount } from "./calculator-shield";
import { ShieldPassiveRow } from "./calculator-shield-controls";
import { useApp } from "./provider";
import { CachedImage } from "./ui";
import type { Action, Player } from "./types";
import {
  CalculatorAppearanceSettings,
  useCalculatorAppearance,
} from "./calculator-appearance-settings";
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
    <CalculatorBoard
      {...props}
      onAction={action}
      appearance="character"
      setup={
        <>
          <CalculatorAppearanceSettings />
          {props.setup}
        </>
      }
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
            onHp={(amount) => {
              intentUntil.current = Date.now() + 5000;
              props.onHp(target, amount);
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
  onHp: (amount: number) => void;
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
  const low = health.ratio <= 0.3;
  const steps = mirrored ? [500, 100, -100, -500] : [-500, -100, 100, 500];
  return (
    <View
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
      <View style={[s.head, mirrored && { flexDirection: "row-reverse" }]}>
        {!!avatar && (
          <View style={[s.avatar, compact && { width: 26, height: 26 }, { borderColor: theme.accent }]}>
            <CachedImage url={avatar} fill height={compact ? 26 : 30} />
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
        <Text maxFontSizeMultiplier={1.2} style={s.hand}>
          {t("손패")} {hand}
        </Text>
      </View>
      <View style={[s.controls, mirrored && { flexDirection: "row-reverse" }]}>
        <View style={s.main}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${label} HP ${player.hp}, ${t("대미지 적용")}`}
            disabled={disabled}
            onPress={onDamage}
            style={[s.hp, { minHeight: compact ? 66 : 104 }]}
          >
            <Text style={[s.caption, { position: "absolute", top: 5, left: 10 }]}>HP</Text>
            <Text
              adjustsFontSizeToFit
              numberOfLines={1}
              maxFontSizeMultiplier={1}
              style={[s.hpValue, { color: player.hp <= 0 ? "#687183" : health.strong, fontSize: compact ? 44 : 72 }]}
            >
              {player.hp}
              {!!shield && <Text style={{ color: "#9fd0ff", fontSize: compact ? 16 : 22 }}> +{shield}</Text>}
            </Text>
            <View style={s.barTrack} pointerEvents="none">
              <View style={[s.bar, { width: `${health.ratio * 100}%`, backgroundColor: health.strong }]} />
            </View>
            {!!pendingHp && (
              <Text
                accessibilityLabel={`${label} ${t("누적 HP 변화")} ${pendingHp}`}
                style={[
                  s.pending,
                  pendingHp < 0
                    ? { color: C.damage, backgroundColor: "rgba(255,111,111,0.14)", borderColor: C.damage }
                    : { color: C.heal, backgroundColor: "rgba(69,208,160,0.14)", borderColor: C.heal },
                ]}
              >
                {pendingHp > 0 ? "+" : "−"}
                {Math.abs(pendingHp)}
              </Text>
            )}
          </Pressable>
          <View style={s.hpButtons}>
            {steps.map((amount) => (
              <Pressable
                key={amount}
                accessibilityRole="button"
                accessibilityLabel={`${label} HP ${amount > 0 ? "+" : ""}${amount}`}
                accessibilityState={{ disabled }}
                disabled={disabled}
                onPress={() => onHp(amount)}
                style={({ pressed }) => [
                  s.hpButton,
                  { minHeight: compact ? 40 : 56 },
                  amount < 0
                    ? { borderColor: "rgba(255,111,111,0.32)", backgroundColor: Math.abs(amount) === 500 ? "#3a1c22" : "#2a181d" }
                    : { borderColor: "rgba(69,208,160,0.3)", backgroundColor: Math.abs(amount) === 500 ? "#123229" : "#11241f" },
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
        </View>
        <View style={[s.fp, { width: compact ? 50 : 72 }]}>
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
      <View style={s.passives}>
        <ShieldPassiveRow player={player} target={target} disabled={disabled} pending={pendingShield} onShield={onShield} onAction={onAction}>
          <PassiveTray
            player={player}
            target={target}
            definition={player.character?.passive || {}}
            disabled={disabled}
            accent={theme.accent}
            secondary={theme.secondary}
            onAction={(value) => void onAction(value)}
          />
        </ShieldPassiveRow>
      </View>
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
      style={({ pressed }) => [s.step, { minHeight: compact ? 36 : 54 }, disabled && { opacity: 0.4 }, pressed && { transform: [{ scale: 0.96 }] }]}
    >
      <Text adjustsFontSizeToFit numberOfLines={1} maxFontSizeMultiplier={1.2} style={[s.stepText, { fontSize: compact ? 18 : 24 }]}>
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
  controls: { flexDirection: "row", gap: 8 },
  main: { flex: 1, minWidth: 0, gap: 6 },
  caption: { color: C.muted, fontSize: 10, fontWeight: "800", letterSpacing: 1.2 },
  hp: {
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingBottom: 8,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: C.line,
    backgroundColor: "rgba(5,7,11,0.62)",
  },
  hpValue: { fontWeight: "900", letterSpacing: -1, fontVariant: ["tabular-nums"] },
  barTrack: { position: "absolute", left: 10, right: 10, bottom: 6, height: 4, borderRadius: 4, backgroundColor: "rgba(255,255,255,0.08)", overflow: "hidden" },
  bar: { height: 4, borderRadius: 4 },
  pending: {
    position: "absolute",
    top: 5,
    right: 8,
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderStyle: "dashed",
    fontWeight: "900",
    fontSize: 15,
    overflow: "hidden",
  },
  fp: { gap: 4 },
  fpValue: {
    flex: 1,
    minHeight: 30,
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
  hpButtons: { flexDirection: "row", gap: 6 },
  hpButton: { flex: 1, minWidth: 0, borderWidth: 1, borderRadius: 12, alignItems: "center", justifyContent: "center", paddingHorizontal: 2 },
  hpStep: { fontWeight: "900", fontVariant: ["tabular-nums"] },
  passives: { flex: 1, minHeight: 0 },
});
