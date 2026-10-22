import React, { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  Animated,
  AppState,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { CalculatorBoard, type CalculatorBoardProps } from "./calculator-board";
import { calculatorTheme } from "./calculator-ui";
import { calculatorArt } from "./calculator-art";
import { localized } from "./core";
import { VisualPassives } from "./calculator-visual-passives";
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
  ambientAllowed,
  display,
}: PlayerProps) {
  const { t } = useApp();
  const { height } = useWindowDimensions();
  const compact = height < 500;
  const theme = calculatorTheme(player.character);
  const art = calculatorArt[theme.theme_key];
  const health = hpAppearance(player.hp, player.initial_hp);
  const label = t(target === "p1" ? "플레이어1" : "플레이어2");
  const table = player.character?.hand_table || {};
  const thresholds = Object.keys(table)
    .map(Number)
    .sort((a, b) => a - b);
  const threshold = thresholds.find((n) => player.hp <= n) ?? thresholds.at(-1);
  const hand = threshold === undefined ? "—" : table[threshold];
  const pulse = useRef(new Animated.Value(0)).current;
  const snapshot = JSON.stringify([
    player.character?.id,
    player.hp,
    player.fp,
    player.passive_state,
  ]);
  const previous = useRef({ snapshot, character: player.character?.id });
  useEffect(() => {
    const before = previous.current;
    previous.current = { snapshot, character: player.character?.id };
    if (
      before.snapshot === snapshot ||
      before.character !== player.character?.id ||
      !motionAllowed()
    )
      return;
    pulse.stopAnimation();
    pulse.setValue(0.75);
    Animated.timing(pulse, {
      toValue: 0,
      duration: 480,
      useNativeDriver: true,
    }).start();
  }, [snapshot]);
  return (
    <View style={[s.player, { borderColor: theme.accent + "88" }]}>
      <View
        pointerEvents="none"
        style={StyleSheet.absoluteFill}
        accessibilityElementsHidden
        importantForAccessibility="no-hide-descendants"
      >
        {art && display.style === "illustrated" && (
          <Image
            key={"scene-" + theme.theme_key}
            source={art.background}
            resizeMode="cover"
            style={[
              StyleSheet.absoluteFill,
              { width: "100%", height: "100%" },
              target === "p1" && { transform: [{ scaleX: -1 }] },
            ]}
            accessibilityElementsHidden
            importantForAccessibility="no-hide-descendants"
          />
        )}
        {display.style === "illustrated" && !!player.character?.img && (
          <View
            pointerEvents="none"
            style={[
              s.portrait,
              target === "p2" && { left: "-8%", right: undefined },
            ]}
          >
            <CachedImage
              key={String(player.character.id) + ":" + player.character.img}
              url={player.character.img}
              fill
              transparent
              height="100%"
              contentPosition={target === "p1" ? "right center" : "left center"}
            />
          </View>
        )}
        <View
          pointerEvents="none"
          style={[
            StyleSheet.absoluteFill,
            {
              backgroundColor: "#080d16",
              opacity:
                display.style === "clean" ? 0 : 1 - display.brightness / 100,
            },
          ]}
        />
      </View>
      <View
        style={[
          s.resources,
          target === "p2" && { flexDirection: "row-reverse" },
        ]}
      >
        <View style={{ flex: 1, minWidth: 0, gap: 4 }}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${label} HP ${player.hp}, ${t("대미지 적용")}`}
            disabled={disabled}
            onPress={onDamage}
            style={[
              s.health,
              { minHeight: compact ? 84 : 108, borderColor: health.border },
            ]}
          >
            <Text
              style={[s.caption, { position: "absolute", top: 5, left: 7 }]}
            >
              HP
            </Text>
            <Text
              style={[
                s.hand,
                {
                  position: "absolute",
                  top: 5,
                  right: 7,
                  color: theme.secondary,
                },
              ]}
            >
              {t("손패")} {hand}
            </Text>
            <Text
              adjustsFontSizeToFit
              numberOfLines={1}
              style={[
                s.hpValue,
                { color: health.strong, fontSize: compact ? 48 : 68 },
              ]}
            >
              {player.hp}
              {!!shieldAmount(player) && <Text style={{ color: "#a9e4ff", fontSize: compact ? 18 : 24 }}> +{shieldAmount(player)}</Text>}
            </Text>
            <View
              pointerEvents="none"
              style={[
                s.healthBar,
                {
                  width: `${health.ratio * 100}%`,
                  backgroundColor: health.strong,
                },
              ]}
            />
            {!!pendingHp && (
              <Text
                style={[
                  s.pending,
                  { color: pendingHp < 0 ? "#ff98aa" : "#98e0c8" },
                ]}
              >
                {pendingHp > 0 ? "+" : "−"}
                {Math.abs(pendingHp)}
              </Text>
            )}
          </Pressable>
          <View style={s.hpButtons}>
            {[-500, -100, 100, 500].map((amount) => (
              <Pressable
                key={amount}
                accessibilityRole="button"
                accessibilityLabel={`${label} HP ${amount > 0 ? "+" : ""}${amount}`}
                accessibilityState={{ disabled }}
                disabled={disabled}
                onPress={() => onHp(amount)}
                style={[
                  s.hpButton,
                  {
                    backgroundColor: amount < 0 ? "#401e31c0" : "#153a35c0",
                    opacity: disabled ? 0.4 : 1,
                  },
                ]}
              >
                <Text
                  adjustsFontSizeToFit
                  numberOfLines={1}
                  style={[
                    s.hpStep,
                    { color: amount < 0 ? "#ff98aa" : "#98e0c8" },
                  ]}
                >
                  {amount > 0 ? "+" : "−"}
                  {Math.abs(amount)}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
        <View style={s.fp}>
          <ArenaButton
            label={`${label} FP +1`}
            text={pendingFp > 0 ? `+${pendingFp}` : "+"}
            accent={theme.accent}
            disabled={disabled}
            onPress={() => onFp(1)}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`${label} FP ${player.fp}, ${t("초기화")}`}
            disabled={disabled}
            onPress={() => onAction({ action: "fp_reset", target })}
            style={s.fpValue}
          >
            <Text style={s.caption}>FP</Text>
            <Text style={[s.fpNumber, { color: theme.secondary }]}>
              {player.fp}
            </Text>
          </Pressable>
          <ArenaButton
            label={`${label} FP -1`}
            text={pendingFp < 0 ? `−${Math.abs(pendingFp)}` : "−"}
            accent={theme.accent}
            disabled={disabled}
            onPress={() => onFp(-1)}
          />
        </View>
      </View>
      <View style={s.passives}>
        <ShieldPassiveRow player={player} target={target} disabled={disabled} pending={pendingShield} onShield={onShield} onAction={onAction}>
        <VisualPassives
          player={player}
          target={target}
          disabled={disabled}
          onAction={onAction}
          accent={theme.accent}
          theme={theme.theme_key}
          clean={display.style === "clean"}
          motionAllowed={() => display.style !== "clean" && motionAllowed()}
          ambientAllowed={display.style !== "clean" && ambientAllowed}
        />
        </ShieldPassiveRow>
      </View>
      <Animated.View
        pointerEvents="none"
        style={[
          StyleSheet.absoluteFill,
          {
            borderWidth: 3,
            borderRadius: 14,
            borderColor: theme.accent,
            opacity: display.style === "clean" ? 0 : pulse,
          },
        ]}
      />
    </View>
  );
}
function ArenaButton({
  label,
  text,
  accent,
  disabled,
  onPress,
  active = false,
}: {
  label: string;
  text: string;
  accent: string;
  disabled: boolean;
  onPress: () => void;
  active?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled, selected: active }}
      disabled={disabled}
      onPress={onPress}
      style={[
        s.button,
        {
          borderColor: accent + "66",
          backgroundColor: active ? accent : "#17243be8",
          opacity: disabled ? 0.4 : 1,
        },
      ]}
    >
      <Text
        adjustsFontSizeToFit
        numberOfLines={2}
        style={[s.buttonText, { color: active ? "#101725" : accent }]}
      >
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
    borderRadius: 14,
    padding: 8,
    gap: 6,
    overflow: "hidden",
    backgroundColor: "#101725",
  },
  portrait: {
    position: "absolute",
    right: "-8%",
    top: 0,
    bottom: "-3%",
    width: "94%",
    opacity: 0.8,
  },
  hand: {
    fontSize: 11,
    fontWeight: "700",
    padding: 0,
  },
  resources: { flexDirection: "row", gap: 6 },
  health: {
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0a1224b8",
    borderWidth: 1,
    borderRadius: 10,
    overflow: "hidden",
  },
  caption: {
    color: "#b3c0d6",
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 1,
  },
  hpValue: {
    fontWeight: "900",
    letterSpacing: -1,
    fontVariant: ["tabular-nums"],
  },
  healthBar: { position: "absolute", left: 0, bottom: 0, height: 4 },
  pending: {
    position: "absolute",
    top: 5,
    left: 30,
    fontWeight: "800",
    fontSize: 12,
    backgroundColor: "#10192bee",
    padding: 3,
    borderRadius: 5,
  },
  hpButtons: { flexDirection: "row", gap: 4 },
  hpButton: {
    flex: 1,
    minWidth: 44,
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#52607966",
    borderRadius: 6,
    paddingHorizontal: 1,
  },
  hpStep: { fontSize: 12, fontWeight: "800" },
  fp: { width: 44, gap: 0 },
  fpValue: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderColor: "#40526b",
    borderRadius: 7,
    backgroundColor: "#0b1428b8",
    alignItems: "center",
    justifyContent: "center",
  },
  fpNumber: { fontSize: 23, fontWeight: "800", fontVariant: ["tabular-nums"] },
  passives: { flex: 1, minHeight: 0 },
  button: {
    minWidth: 44,
    minHeight: 44,
    borderWidth: 1,
    borderRadius: 7,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 3,
  },
  buttonText: { fontSize: 13, fontWeight: "800", textAlign: "center" },
});
