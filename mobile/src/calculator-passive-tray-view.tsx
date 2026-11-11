import React, { useEffect, useState } from "react";
import { Image, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import type { Action, PassiveDefinition, Player } from "./types";
import { passiveTray, pipValue, trayAction, type TrayItem } from "./calculator-passive-tray";
import { passiveLineIcons } from "./calculator-line-icons";
import { passiveArtImages } from "./calculator-clean-art";
import { useApp } from "./provider";

const WORDS: Record<string, Record<string, string>> = {
  ko: { on: "ON", off: "OFF", use: "발동", using: "발동 중", ready: "사용 가능", none: "조작할 패시브가 없습니다." },
  en: { on: "ON", off: "OFF", use: "Use", using: "Active", ready: "Ready", none: "No passive to track." },
  ja: { on: "ON", off: "OFF", use: "発動", using: "発動中", ready: "使用可", none: "操作するパッシブはありません。" },
};
const GOLD = "#e8bd62";

/**
 * 웹 calculator-hud.js와 같은 패시브 트레이. 스크롤하지 않고 남은 높이에 맞춘다:
 * 넘치면 안내 문구를 숨기고(1단계), 아이콘을 빼고 두 칸씩 배치한다(2단계).
 */
export function PassiveTray({
  player,
  target,
  definition,
  disabled,
  accent,
  secondary,
  onAction,
}: {
  player: Player;
  target: "p1" | "p2";
  definition: PassiveDefinition;
  disabled: boolean;
  accent: string;
  secondary: string;
  onAction: (action: Action) => void;
}) {
  const { language } = useApp();
  const words = WORDS[language] || WORDS.ko!;
  const items = passiveTray(player, definition, language);
  const send = (key: string, value: unknown) => {
    const action = trayAction(player, definition, target, key, value, language);
    if (action) onAction(action);
  };
  const [box, setBox] = useState(0);
  const [content, setContent] = useState(0);
  // 0 크게 · 1 넉넉하게 · 2 기본 · 3 안내 숨김 · 4 두 칸 배치. 들어가는 가장 큰 단계를 고른다.
  const [step, setStep] = useState(0);
  const grow = Math.max(0, 2 - step);
  const level = Math.max(0, step - 2);
  const shape = items.map((i) => i.key + (i.hint ? "+" : "")).join(",");
  // 항목 구성이나 공간이 바뀌면 가장 큰 모양부터 다시 맞춰 본다.
  useEffect(() => setStep(0), [shape, box]);
  useEffect(() => {
    if (box > 0 && content > box + 1 && step < 4) setStep(step + 1);
  }, [content, box, step]);
  return (
    <View style={s.box} onLayout={(e) => setBox(Math.round(e.nativeEvent.layout.height))}>
      <View style={[s.tray, level === 2 && { gap: 4 }, grow > 0 && { gap: 8 }]} onLayout={(e) => setContent(Math.round(e.nativeEvent.layout.height))}>
        {items.map((item) => (
          <Item
            key={item.key}
            item={item}
            words={words}
            accent={accent}
            secondary={secondary}
            level={level}
            grow={grow}
            locked={disabled}
            send={send}
          />
        ))}
        {!items.length && !!player.character && <Text style={s.empty}>{words.none}</Text>}
      </View>
    </View>
  );
}

function Item({
  item,
  words,
  accent,
  secondary,
  level,
  grow,
  locked,
  send,
}: {
  item: TrayItem;
  words: Record<string, string>;
  accent: string;
  secondary: string;
  level: number;
  grow: number;
  locked: boolean;
  send: (key: string, value: unknown) => void;
}) {
  const blocked = locked || !item.enabled;
  const half = ["toggle", "trigger", "status"].includes(item.kind) || level === 2;
  const card = [
    s.card,
    half ? s.half : s.full,
    level >= 1 && { paddingVertical: 5 },
    level === 2 && { paddingHorizontal: 7, paddingVertical: 3, borderRadius: 9 },
    grow > 0 && { paddingHorizontal: 12, paddingVertical: 10, gap: 8, borderRadius: 14 },
    item.active && { borderColor: accent + "c0", backgroundColor: accent + "33" },
    item.kind === "status" && s.status,
    item.attention && { borderColor: GOLD, borderWidth: 2 },
  ];
  // 넉넉한 단계에서는 선 아이콘 대신 패시브 그림을 크게 보여 버튼을 구분하게 한다.
  const picture = grow > 0 && item.art ? passiveArtImages[item.art] : undefined;
  const pictureSize = grow === 2 ? 60 : 44;
  const icon = !picture && item.symbol && level < 2 ? passiveLineIcons[item.symbol] : undefined;
  const pill = (text: string) => (
    <Text
      style={[
        s.pill,
        item.active && { backgroundColor: accent, borderColor: accent, color: "#111" },
        item.attention && !item.active && { borderColor: GOLD, color: GOLD },
      ]}
    >
      {text}
    </Text>
  );
  const head = (extra?: React.ReactNode, inline = false) => (
    <View style={[s.head, inline && level < 2 && !grow && { flexShrink: 1, maxWidth: "42%" }]}>
      {picture !== undefined && (
        <Image
          source={picture}
          resizeMode="contain"
          style={[
            { width: pictureSize, height: pictureSize, borderRadius: 10, opacity: item.active ? 1 : 0.55 },
            item.active && { borderWidth: 2, borderColor: accent },
          ]}
          accessibilityIgnoresInvertColors
        />
      )}
      {icon !== undefined && (
        <Image source={icon} style={[s.icon, grow > 0 && { width: 24, height: 24 }, { opacity: item.active ? 1 : 0.55 }]} accessibilityIgnoresInvertColors />
      )}
      <Text
        numberOfLines={1}
        maxFontSizeMultiplier={1.2}
        style={[s.name, level === 2 && { fontSize: 12 }, grow > 0 && { fontSize: grow === 2 ? 17 : 15.5 }, !item.enabled && !item.active && item.kind !== "status" && s.muted]}
      >
        {item.label}
      </Text>
      {extra}
    </View>
  );
  const hint =
    item.hint && level === 0 ? (
      <Text numberOfLines={1} maxFontSizeMultiplier={1.2} style={s.hint}>
        {item.hint}
      </Text>
    ) : null;
  const small = level === 2;
  // 확대 단계에서 누르는 칸의 높이
  const tap = grow === 2 ? 58 : grow === 1 ? 44 : 0;
  const pressHeight = grow === 2 ? 84 : grow === 1 ? 64 : small ? 32 : level ? 38 : 46;
  // 확대 단계에서는 이름 줄 아래에 조작 줄을 통째로 둔다.
  const stacked = small || grow > 0;
  const lineStyle = stacked ? { gap: grow ? 8 : 3 } : s.line;
  // 세로로 쌓을 때 flex: 1이 남으면 높이 기준이 0이 되어 칸 줄이 카드 밖으로 넘친다(이름 줄과 겹침).
  // 세로로 쌓을 때는 flex를 아예 쓰지 않고(높이 기준 0 방지) 줄 높이를 명시한다.
  const rowFill = stacked
    ? { flexGrow: 0, flexShrink: 0, flexBasis: "auto" as const, alignSelf: "stretch" as const }
    : { flexGrow: 1, flexShrink: 1, flexBasis: 0 };

  if (item.kind === "toggle" || item.kind === "trigger") {
    const trigger = item.kind === "trigger";
    const state = trigger
      ? item.active ? words.using : item.ready ? words.ready : words.use
      : item.active ? words.on : words.off;
    return (
      <Pressable
        accessibilityRole={trigger ? "button" : "switch"}
        accessibilityLabel={`${item.label} ${state}`}
        accessibilityHint={item.hint || undefined}
        accessibilityState={{ disabled: blocked, checked: trigger ? undefined : item.active, selected: trigger ? item.active : undefined }}
        disabled={blocked}
        onPress={() => send(item.key, !item.active)}
        style={({ pressed }) => [card, { minHeight: pressHeight, justifyContent: "center" }, pressed && { opacity: 0.8 }]}
      >
        {head(pill(state!))}
        {hint}
      </Pressable>
    );
  }
  if (item.kind === "status")
    return (
      <View
        accessible
        accessibilityRole="text"
        accessibilityLabel={`${item.label} ${item.active ? words.on : words.off}. ${item.hint}`}
        style={[card, { minHeight: grow ? 52 : small ? 32 : level ? 38 : 46, justifyContent: "center" }]}
      >
        {head(pill((item.active ? words.on : words.off)!))}
        {hint}
      </View>
    );
  if (item.kind === "counter") {
    const value = Number(item.value) || 0;
    const count = item.max ? `${value}/${item.max}` : `${value}${item.unit || ""}`;
    const pipHeight = tap || (small ? 20 : level ? 24 : 28);
    return (
      <View style={card}>
        <View style={lineStyle}>
          {head(<Text style={[s.count, grow > 0 && { fontSize: 16 }, item.active && { color: secondary }]}>{count}</Text>, true)}
          <View style={[s.counter, rowFill, { minHeight: Math.max(pipHeight, tap || (small ? 26 : 32)) }, grow > 0 && { gap: 8 }]}>
            <Step small={small} size={tap} label={`${item.label} −1`} text="−" disabled={blocked || value <= 0} onPress={() => send(item.key, value - 1)} />
            {item.max && item.max <= 12 ? (
              <View style={s.pips}>
                {Array.from({ length: item.max }, (_, index) => (
                  <Pressable
                    key={index}
                    accessibilityRole="button"
                    accessibilityLabel={`${item.label} ${pipValue(value, index)}`}
                    accessibilityState={{ disabled: blocked, selected: index < value }}
                    disabled={blocked}
                    hitSlop={{ top: 6, bottom: 6 }}
                    onPress={() => send(item.key, pipValue(value, index))}
                    style={[
                      s.pip,
                      { height: pipHeight },
                      index < value && { backgroundColor: accent, borderColor: accent },
                      blocked && { opacity: 0.55 },
                    ]}
                  />
                ))}
              </View>
            ) : (
              <Text style={s.counterValue}>{value}</Text>
            )}
            <Step
              small={small}
              size={tap}
              label={`${item.label} +1`}
              text="+"
              disabled={blocked || (item.max != null && value >= item.max)}
              onPress={() => send(item.key, value + 1)}
            />
          </View>
        </View>
        {hint}
      </View>
    );
  }
  if (item.kind === "choice")
    return (
      <View style={card}>
        <View style={lineStyle}>
          {head(undefined, true)}
          <View
            accessibilityRole="radiogroup"
            style={[s.choices, rowFill, { minHeight: (tap || (small ? 24 : level ? 28 : 32)) + 6 }]}
          >
            {(item.choices || []).map((choice) => (
              <Pressable
                key={choice.value}
                accessibilityRole="radio"
                accessibilityLabel={`${item.label} ${choice.label}`}
                accessibilityState={{ checked: choice.selected, disabled: blocked }}
                disabled={blocked}
                onPress={() => send(item.key, choice.value)}
                style={[
                  s.choice,
                  { minHeight: tap || (small ? 24 : level ? 28 : 32) },
                  grow > 0 && !!choice.art && { minHeight: grow === 2 ? 86 : 70, gap: 3, paddingVertical: 4 },
                  choice.selected && { backgroundColor: accent },
                  blocked && !choice.selected && { opacity: 0.4 },
                ]}
              >
                {grow > 0 && choice.art && passiveArtImages[choice.art] !== undefined && (
                  <Image
                    source={passiveArtImages[choice.art]!}
                    resizeMode="contain"
                    style={{ width: grow === 2 ? 48 : 36, height: grow === 2 ? 48 : 36, borderRadius: 8, opacity: choice.selected ? 1 : 0.6 }}
                    accessibilityIgnoresInvertColors
                  />
                )}
                <Text numberOfLines={1} adjustsFontSizeToFit maxFontSizeMultiplier={1.2} style={[s.choiceText, choice.selected && { color: "#111" }]}>
                  {choice.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
        {hint}
      </View>
    );
  return (
    <View style={card}>
      {head()}
      <TextInput
        accessibilityLabel={item.label}
        editable={!blocked}
        defaultValue={String(item.value ?? "")}
        onEndEditing={(e) => send(item.key, e.nativeEvent.text)}
        style={s.input}
      />
    </View>
  );
}

function Step({ label, text, disabled, small, size = 0, onPress }: { label: string; text: string; disabled: boolean; small: boolean; size?: number; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
      disabled={disabled}
      hitSlop={4}
      onPress={onPress}
      style={[s.step, small && { width: 26, height: 26 }, size > 0 && { width: size, height: size, borderRadius: 12 }, disabled && { opacity: 0.35 }]}
    >
      <Text style={[s.stepText, size > 0 && { fontSize: size > 50 ? 26 : 22 }]}>{text}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  box: { flex: 1, minHeight: 0, overflow: "hidden" },
  tray: { flexDirection: "row", flexWrap: "wrap", gap: 6, alignContent: "flex-start" },
  empty: { color: "#687183", fontSize: 12, textAlign: "center", padding: 8, width: "100%" },
  card: {
    gap: 4,
    paddingVertical: 7,
    paddingHorizontal: 10,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.09)",
    backgroundColor: "rgba(9,12,18,0.78)",
  },
  full: { width: "100%" },
  half: { flexGrow: 1, flexBasis: "45%", minWidth: 0 },
  status: { borderStyle: "dashed" },
  head: { flexDirection: "row", alignItems: "center", gap: 7, minWidth: 0 },
  icon: { width: 20, height: 20 },
  name: { flexShrink: 1, color: "#f2f0ea", fontSize: 13.5, fontWeight: "800" },
  muted: { color: "#9ba4b4" },
  hint: { color: "#9ba4b4", fontSize: 11 },
  pill: {
    marginLeft: "auto",
    minWidth: 34,
    paddingVertical: 2,
    paddingHorizontal: 7,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    color: "#9ba4b4",
    fontSize: 10.5,
    fontWeight: "900",
    textAlign: "center",
    overflow: "hidden",
  },
  count: { color: "#9ba4b4", fontSize: 13.5, fontWeight: "900", fontVariant: ["tabular-nums"] },
  line: { flexDirection: "row", alignItems: "center", gap: 10 },
  counter: { flexDirection: "row", alignItems: "center", gap: 5, minWidth: 0 },
  counterValue: { flex: 1, color: "#f2f0ea", fontSize: 20, fontWeight: "900", textAlign: "center", fontVariant: ["tabular-nums"] },
  pips: { flex: 1, flexDirection: "row", gap: 4, minWidth: 0 },
  pip: {
    flex: 1,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    backgroundColor: "rgba(255,255,255,0.04)",
  },
  step: {
    width: 32,
    height: 32,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.09)",
    backgroundColor: "rgba(255,255,255,0.055)",
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { color: "#f2f0ea", fontSize: 17, fontWeight: "800" },
  choices: { flexDirection: "row", gap: 3, padding: 3, borderRadius: 10, backgroundColor: "rgba(255,255,255,0.05)" },
  choice: { flex: 1, borderRadius: 8, alignItems: "center", justifyContent: "center", paddingHorizontal: 4 },
  choiceText: { color: "#9ba4b4", fontSize: 12.5, fontWeight: "800" },
  input: {
    minHeight: 34,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.09)",
    backgroundColor: "rgba(0,0,0,0.3)",
    color: "#f2f0ea",
    paddingHorizontal: 10,
  },
});
