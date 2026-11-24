import React, { useEffect, useMemo, useState } from "react";
import { Image, Pressable, StyleSheet, Text, TextInput, View, type ViewStyle } from "react-native";
import type { Action, PassiveDefinition, Player } from "./types";
import { passiveTray, trayAction, type TrayItem } from "./calculator-passive-tray";
import { TOKEN_CROP, cardCrop, passiveCardImage, passiveGroups, passiveLayout, withCalculatorExtras, type PassiveGroup } from "./calculator-layout";
import { passiveArtImages } from "./calculator-clean-art";
import { cachedImage } from "./catalog";
import { absoluteUrl } from "./api";
import { useApp } from "./provider";

const WORDS: Record<string, Record<string, string>> = {
  ko: { on: "ON", off: "OFF", use: "발동", using: "발동 중", ready: "사용 가능", reset: "눌러서 초기화" },
  en: { on: "ON", off: "OFF", use: "Use", using: "Active", ready: "Ready", reset: "tap to reset" },
  ja: { on: "ON", off: "OFF", use: "発動", using: "発動中", ready: "使用可", reset: "タップでリセット" },
};
const GOLD = "#e8bd62";
const CARD_RATIO = 1117 / 821;
const FILL = { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 } as const;

/**
 * 웹 calculator-hud.js와 같은 패시브: 카드 그림 일부 + 불빛 + ±.
 * 1개는 크게, 2개는 둘로 나누고, 그 외는 목록. 높이는 maxHeight까지만 쓰고, 넘치면 이름 → 그림 순으로 줄인다.
 */
export function PassiveTray({
  player,
  target,
  definition: rawDefinition,
  disabled,
  accent,
  maxHeight,
  large = false,
  onAction,
}: {
  player: Player;
  target: "p1" | "p2";
  definition: PassiveDefinition;
  disabled: boolean;
  accent: string;
  maxHeight: number;
  /** 태블릿 등 큰 화면: 칸과 버튼을 크게 하고 짝 카운터(타오)는 한 줄씩 펼친다. */
  large?: boolean;
  onAction: (action: Action) => void;
}) {
  const { language, catalog } = useApp();
  const words = WORDS[language] || WORDS.ko!;
  // 예전 카탈로그·공유 계산기에도 토큰 카드 그림과 최대 개수 보정을 앱 카탈로그로 채운다.
  const character: any = player.character;
  const definition = useMemo(() => {
    const korean: Record<string, string> = {};
    for (const control of character?.localized?.ko?.passive?.controls || []) if (control?.key) korean[control.key] = control.label;
    return withCalculatorExtras(rawDefinition, character?.id, catalog?.cards, korean);
  }, [rawDefinition, character?.id, catalog?.cards]);
  const items = passiveTray(player, definition, language);
  const send = (key: string, value: unknown) => {
    const action = trayAction(player, definition, target, key, value, language);
    if (action) onAction(action);
  };
  const image = useCardImage(passiveCardImage(player.character));
  const theme = String(player.character?.calculator_ui?.theme_key || "");
  const [content, setContent] = useState(0);
  const [level, setLevel] = useState(0);
  const shape = items.map((i) => i.key).join(",");
  useEffect(() => setLevel(0), [shape, maxHeight]);
  useEffect(() => {
    if (maxHeight > 0 && content > maxHeight + 1 && level < 2) setLevel(level + 1);
  }, [content, maxHeight, level]);
  if (!items.length) return null;
  const mode = passiveLayout(items);
  const ctx: Ctx = { image, theme, accent, words, locked: disabled, send, level, large, indexOf: (item) => items.indexOf(item) };
  const groups = passiveGroups(items);
  return (
    <View style={{ maxHeight, overflow: "hidden" }}>
      <View
        onLayout={(e) => setContent(Math.round(e.nativeEvent.layout.height))}
        style={mode === "list" ? [s.listFrame, large && { padding: 8, gap: 8 }] : { flexDirection: "row", gap: large ? 8 : 6 }}
      >
        {mode === "list" && image ? (
          <>
            <CardCrop ctx={ctx} cropKey={items[0]?.key || "list"} index={0} lit style={{ ...FILL, opacity: 0.45, borderRadius: 0 }} />
            <View style={[FILL, { backgroundColor: "rgba(8,10,15,0.72)" }]} />
          </>
        ) : null}
        {mode === "list"
          ? groups.map((group, i) => <ListRow key={i} group={group} ctx={ctx} />)
          : items.map((item) => <Tile key={item.key} item={item} ctx={ctx} size={mode === "hero" ? "hero" : "split"} />)}
      </View>
    </View>
  );
}

type Ctx = {
  image: string;
  theme: string;
  accent: string;
  words: Record<string, string>;
  locked: boolean;
  send: (key: string, value: unknown) => void;
  level: number;
  large: boolean;
  indexOf: (item: TrayItem) => number;
};

/** 카드 그림을 기기에 받아 두고 로컬 경로를 쓴다(오프라인에서도 보이게). */
function useCardImage(url: string) {
  const [source, setSource] = useState(url ? absoluteUrl(url) : "");
  useEffect(() => {
    let live = true;
    setSource(url ? absoluteUrl(url) : "");
    if (url)
      cachedImage(url, false)
        .then((path) => {
          if (live && path) setSource(path);
        })
        .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [url]);
  return source;
}

/** 카드 그림의 일부를 칸 크기에 맞춰 자른다(폭 기준, 찌그러짐 없음). */
function CardCrop({
  ctx,
  cropKey,
  index,
  lit,
  style,
  art,
  token,
}: {
  ctx: Ctx;
  cropKey: string;
  index: number;
  lit: boolean;
  style?: ViewStyle;
  art?: string;
  /** 토큰 카운터면 그 토큰 카드 그림을 쓴다. */
  token?: string;
}) {
  const [width, setWidth] = useState(0);
  const tokenImage = useCardImage(token || "");
  const image = tokenImage || ctx.image;
  const area = tokenImage ? TOKEN_CROP : cardCrop(ctx.theme, cropKey, index);
  const fallback = !image && art ? passiveArtImages[art] : undefined;
  const imageWidth = width / area.w;
  const imageHeight = imageWidth * CARD_RATIO;
  return (
    <View
      pointerEvents="none"
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      style={[s.crop, { opacity: lit ? 1 : 0.55 }, style]}
    >
      {!!image && width > 0 && (
        <Image
          source={{ uri: image }}
          style={{ position: "absolute", width: imageWidth, height: imageHeight, left: -area.x * imageWidth, top: -area.y * imageHeight }}
        />
      )}
      {fallback !== undefined && <Image source={fallback} resizeMode="contain" style={StyleSheet.absoluteFill} />}
    </View>
  );
}

function stateText(item: TrayItem, words: Record<string, string>) {
  if (item.kind === "trigger") return item.active ? words.using! : item.ready ? words.ready! : words.use!;
  return item.active ? words.on! : words.off!;
}
const frame = (item: TrayItem, accent: string) => [
  item.active && { borderColor: accent, borderWidth: 2 },
  item.attention && { borderColor: GOLD, borderWidth: 2 },
  item.kind === "status" && { borderStyle: "dashed" as const },
];

/**
 * 카운터 박스 전체가 초기화 버튼(누르면 0). 안쪽 ± 버튼은 hitSlop으로 박스 쪽까지 넓혀,
 * ± 가까운 곳을 누르면 초기화가 아니라 ±로 동작한다.
 */
function ResetBox({
  item,
  ctx,
  style,
  edges,
  children,
}: {
  item: TrayItem;
  ctx: Ctx;
  style: any;
  /** 박스 바깥 ± 버튼과 맞닿은 가장자리: "sides"는 왼쪽 −/오른쪽 +, "bottom"은 아래 ± 막대(초기화하지 않음). */
  edges?: "sides" | "bottom";
  children: React.ReactNode;
}) {
  const value = Number(item.value) || 0;
  const blocked = ctx.locked || !item.enabled;
  const [size, setSize] = useState({ width: 0, height: 0 });
  const EDGE = 16;
  const press = (x: number, y: number) => {
    if (edges === "sides" && size.width > EDGE * 3 && (x < EDGE || x > size.width - EDGE)) {
      const next = value + (x < EDGE ? -1 : 1);
      if (next >= 0 && (item.max == null || next <= item.max)) ctx.send(item.key, next);
      return;
    }
    if (edges === "bottom" && y > size.height - 12) return;
    if (value > 0) ctx.send(item.key, 0);
  };
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.label} ${value}${item.hint ? `, ${item.hint}` : ""}, ${ctx.words.reset}`}
      accessibilityState={{ disabled: blocked || value <= 0 }}
      disabled={blocked}
      pointerEvents={edges ? "box-only" : "auto"}
      onLayout={(e) => setSize({ width: e.nativeEvent.layout.width, height: e.nativeEvent.layout.height })}
      onPress={(e) => press(e.nativeEvent.locationX, e.nativeEvent.locationY)}
      accessibilityActions={[{ name: "activate" }]}
      onAccessibilityAction={() => value > 0 && ctx.send(item.key, 0)}
      style={({ pressed }) => [style, pressed && { opacity: 0.8 }]}
    >
      {children}
    </Pressable>
  );
}

/** 개수 표시(불빛·×N). 누르는 곳은 이걸 담은 박스 전체다(ResetBox). */
function Lights({ item, ctx, big = false }: { item: TrayItem; ctx: Ctx; big?: boolean }) {
  const value = Number(item.value) || 0;
  const counted = !item.max || item.max > 12;
  const size = ctx.large ? (big ? 24 : 22) : big ? 16 : ctx.level === 2 ? 11 : 14;
  const yin = item.key === "yin_counter";
  const yang = item.key === "yang_counter";
  return (
    <View pointerEvents="none" style={[s.lights, ctx.large && { gap: 10 }]}>
      {counted ? (
        <Text style={[s.count, big && { fontSize: 22 }, ctx.large && { fontSize: 28 }]}>×{value}</Text>
      ) : (
        Array.from({ length: item.max || 0 }, (_, index) => {
          const on = index < value;
          return (
            <View
              key={index}
              style={[
                { width: size, height: size, borderRadius: size / 2, borderWidth: 1, borderColor: "rgba(255,255,255,0.3)", backgroundColor: "rgba(5,7,11,0.75)", alignItems: "center", justifyContent: "center" },
                on && { backgroundColor: ctx.accent, borderColor: ctx.accent },
                (yin || yang) && !on && { borderWidth: 0, backgroundColor: "transparent" },
                on && yang && { backgroundColor: "#f4f1ea", borderColor: "#f4f1ea" },
                on && yin && { backgroundColor: "#050608", borderColor: "#c9c3b6", borderWidth: 2 },
              ]}
            >
              {!on && (yin || yang) && <View style={{ width: size * 0.4, height: size * 0.4, borderRadius: size, backgroundColor: "rgba(255,255,255,0.32)" }} />}
            </View>
          );
        })
      )}
    </View>
  );
}
function Step({ item, delta, ctx, style }: { item: TrayItem; delta: number; ctx: Ctx; style?: ViewStyle }) {
  const value = Number(item.value) || 0;
  const disabled = ctx.locked || !item.enabled || (delta < 0 ? value <= 0 : item.max != null && value >= item.max);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.label} ${delta < 0 ? "−1" : "+1"}`}
      accessibilityState={{ disabled }}
      disabled={disabled}
      hitSlop={{ top: 8, bottom: 8, left: 12, right: 12 }}
      onPress={() => ctx.send(item.key, value + delta)}
      style={({ pressed }) => [s.step, style, disabled && { opacity: 0.35 }, pressed && { transform: [{ scale: 0.95 }] }]}
    >
      <Text style={[s.stepText, ctx.large && { fontSize: 28 }]}>{delta < 0 ? "−" : "+"}</Text>
    </Pressable>
  );
}
function Pill({ item, ctx }: { item: TrayItem; ctx: Ctx }) {
  return (
    <Text
      style={[
        s.pill,
        item.active && { backgroundColor: ctx.accent, borderColor: ctx.accent, color: "#111" },
        item.attention && !item.active && { borderColor: GOLD, color: GOLD },
      ]}
    >
      {stateText(item, ctx.words)}
    </Text>
  );
}

/** 크게 1개 / 둘로 나누기의 카드 한 장 */
function Tile({ item, ctx, size }: { item: TrayItem; ctx: Ctx; size: "hero" | "split" }) {
  const index = ctx.indexOf(item);
  const height = ctx.large
    ? size === "hero" ? (ctx.level ? 120 : 150) : ctx.level ? 160 : 200
    : size === "hero" ? (ctx.level ? 58 : 72) : ctx.level ? 78 : 96;
  const name = ctx.level === 0 ? <Text numberOfLines={1} style={[s.tileName, ctx.large && { fontSize: 15 }]}>{item.label}</Text> : null;
  const label = `${item.label} ${stateText(item, ctx.words)}${item.hint ? `, ${item.hint}` : ""}`;
  if (item.kind === "counter") {
    const face = (
      <ResetBox item={item} ctx={ctx} edges={size === "hero" ? "sides" : "bottom"} style={[s.tile, { flex: 1 }, frame(item, ctx.accent)]}>
        <CardCrop ctx={ctx} cropKey={item.key} index={index} lit={item.active} art={item.art} token={item.token} style={FILL} />
        <View style={s.shade} />
        {name}
        <Lights item={item} ctx={ctx} big={size === "hero"} />
      </ResetBox>
    );
    return size === "hero" ? (
      <View accessibilityLabel={label} style={{ flex: 1, height, flexDirection: "row", gap: 6 }}>
        <Step item={item} delta={-1} ctx={ctx} style={{ width: ctx.large ? 88 : 56 }} />
        {face}
        <Step item={item} delta={1} ctx={ctx} style={{ width: ctx.large ? 88 : 56 }} />
      </View>
    ) : (
      <View accessibilityLabel={label} style={{ flex: 1, height, gap: 5 }}>
        {face}
        <View style={{ flexDirection: "row", gap: ctx.large ? 8 : 5, height: ctx.large ? 52 : 30 }}>
          <Step item={item} delta={-1} ctx={ctx} style={{ flex: 1 }} />
          <Step item={item} delta={1} ctx={ctx} style={{ flex: 1 }} />
        </View>
      </View>
    );
  }
  if (item.kind === "choice")
    return (
      <View accessibilityRole="radiogroup" accessibilityLabel={item.label} style={{ flex: 1, height, flexDirection: "row", gap: 5 }}>
        {(item.choices || []).map((choice, i) => {
          const blocked = ctx.locked || !item.enabled;
          const art = choice.art ? passiveArtImages[choice.art] : undefined;
          return (
            <Pressable
              key={choice.value}
              accessibilityRole="radio"
              accessibilityLabel={`${item.label} ${choice.label}`}
              accessibilityState={{ checked: choice.selected, disabled: blocked }}
              disabled={blocked}
              onPress={() => ctx.send(item.key, choice.value)}
              style={[s.tile, { flex: 1, justifyContent: "flex-end", alignItems: "center" }, choice.selected && { borderColor: ctx.accent, borderWidth: 2 }, blocked && !choice.selected && { opacity: 0.45 }]}
            >
              {art !== undefined ? (
                <Image source={art} resizeMode="contain" style={[StyleSheet.absoluteFill, { opacity: choice.selected ? 1 : 0.55 }]} />
              ) : (
                <CardCrop ctx={ctx} cropKey={`${item.key}:${choice.value}`} index={index + i} lit={choice.selected} style={FILL} />
              )}
              <View style={s.shade} />
              <Text numberOfLines={1} style={s.tileName}>{choice.label}</Text>
            </Pressable>
          );
        })}
      </View>
    );
  if (item.kind === "text")
    return (
      <TextInput
        accessibilityLabel={item.label}
        editable={!(ctx.locked || !item.enabled)}
        defaultValue={String(item.value ?? "")}
        placeholder={item.label}
        onEndEditing={(e) => ctx.send(item.key, e.nativeEvent.text)}
        style={[s.input, { flex: 1 }]}
      />
    );
  const body = (
    <>
      <CardCrop ctx={ctx} cropKey={item.key} index={index} lit={item.active} art={item.art} token={item.token} style={FILL} />
      <View style={s.shade} />
      <View style={s.tileFoot}>
        {name || <View />}
        <Pill item={item} ctx={ctx} />
      </View>
    </>
  );
  if (item.kind === "status")
    return (
      <View accessible accessibilityRole="text" accessibilityLabel={label} style={[s.tile, { flex: 1, height }, frame(item, ctx.accent)]}>
        {body}
      </View>
    );
  const blocked = ctx.locked || !item.enabled;
  return (
    <Pressable
      accessibilityRole={item.kind === "toggle" ? "switch" : "button"}
      accessibilityLabel={label}
      accessibilityState={{ disabled: blocked, checked: item.kind === "toggle" ? item.active : undefined }}
      disabled={blocked}
      onPress={() => ctx.send(item.key, !item.active)}
      style={({ pressed }) => [s.tile, { flex: 1, height }, frame(item, ctx.accent), pressed && { transform: [{ scale: 0.98 }] }]}
    >
      {body}
    </Pressable>
  );
}

/** 목록의 한 줄: 작은 카운터 둘은 반씩, 상태 + 선택지는 한 줄 */
function ListRow({ group, ctx }: { group: PassiveGroup; ctx: Ctx }) {
  const thumb = (item: TrayItem, lit: boolean) =>
    ctx.level < 2 ? <CardCrop ctx={ctx} cropKey={item.key} index={ctx.indexOf(item)} lit={lit} art={item.art} token={item.token} style={s.thumb} /> : null;
  const name = (text: string, wide = false) =>
    ctx.level === 0 || wide ? (
      <Text numberOfLines={1} style={[s.rowName, wide && { maxWidth: undefined }, ctx.large && { fontSize: 16, paddingLeft: 8 }]}>{text}</Text>
    ) : null;
  const big = ctx.large ? s.rowPartLarge : null;
  const stepStyle = ctx.large ? s.rowStepLarge : s.rowStep;
  const counter = (item: TrayItem, paired: boolean) => (
    <ResetBox key={item.key} item={item} ctx={ctx} style={[s.rowPart, big, frame(item, ctx.accent)]}>
      {!paired && thumb(item, item.active)}
      {name(item.label, paired)}
      <Step item={item} delta={-1} ctx={ctx} style={stepStyle} />
      <View pointerEvents="none" style={{ flex: 1, alignItems: "center" }}>
        <Lights item={item} ctx={ctx} />
      </View>
      <Step item={item} delta={1} ctx={ctx} style={stepStyle} />
    </ResetBox>
  );
  // 큰 화면에서는 짝 카운터를 한 줄씩 펼쳐 불빛과 ± 버튼을 키운다.
  if (group.kind === "pair")
    return <View style={[s.row, ctx.large && { flexDirection: "column", gap: 8 }]}>{group.items.map((item) => counter(item, true))}</View>;
  if (group.kind === "status-choice") {
    const { status, choice } = group;
    const blocked = ctx.locked || !choice.enabled;
    return (
      <View style={s.row}>
        <View
          accessibilityLabel={`${status.label} ${stateText(status, ctx.words)}, ${status.hint}`}
          style={[s.rowPart, big, status.active && { borderColor: ctx.accent }, choice.attention && { borderColor: GOLD, borderWidth: 2 }]}
        >
          <View style={[s.lamp, ctx.large && { width: 12, height: 12, borderRadius: 6, marginLeft: 8 }, status.active && { backgroundColor: ctx.accent }]} />
          {name(status.label)}
          <View accessibilityRole="radiogroup" style={s.segment}>
            {(choice.choices || []).map((option) => (
              <Pressable
                key={option.value}
                accessibilityRole="radio"
                accessibilityLabel={`${choice.label} ${option.label}`}
                accessibilityState={{ checked: option.selected, disabled: blocked }}
                disabled={blocked}
                onPress={() => ctx.send(choice.key, option.value)}
                style={[
                  s.rowChoice,
                  ctx.level === 2 && { height: 22 },
                  ctx.large && { height: 44, borderRadius: 8 },
                  option.selected && { backgroundColor: status.active ? ctx.accent : "rgba(255,255,255,0.12)" },
                  blocked && !option.selected && { opacity: 0.4 },
                ]}
              >
                <Text numberOfLines={1} adjustsFontSizeToFit style={[s.rowChoiceText, ctx.large && { fontSize: 16 }, option.selected && { color: status.active ? "#111" : "#f2f0ea" }]}>
                  {option.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      </View>
    );
  }
  const item = group.item;
  if (item.kind === "counter") return <View style={s.row}>{counter(item, false)}</View>;
  return (
    <View style={[s.row, { height: ctx.level === 2 ? 28 : 34 }]}>
      <Tile item={item} ctx={{ ...ctx, level: 1 }} size="hero" />
    </View>
  );
}

const s = StyleSheet.create({
  crop: { overflow: "hidden", backgroundColor: "#2a2418", borderRadius: 9 },
  tile: {
    overflow: "hidden",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    backgroundColor: "#15181f",
    padding: 7,
    justifyContent: "flex-end",
    gap: 4,
  },
  shade: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, backgroundColor: "rgba(5,7,11,0.35)" },
  tileName: { color: "#f2f0ea", fontSize: 12.5, fontWeight: "800", textShadowColor: "#000", textShadowRadius: 3 },
  tileFoot: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 6 },
  pill: {
    paddingVertical: 2,
    paddingHorizontal: 8,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    backgroundColor: "rgba(5,7,11,0.7)",
    color: "#9ba4b4",
    fontSize: 10.5,
    fontWeight: "900",
    overflow: "hidden",
  },
  lights: { flexDirection: "row", flexWrap: "wrap", gap: 5, alignItems: "center" },
  count: { color: "#f2f0ea", fontSize: 18, fontWeight: "900", textShadowColor: "#000", textShadowRadius: 4 },
  step: {
    minWidth: 28,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.09)",
    backgroundColor: "rgba(9,12,18,0.85)",
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { color: "#f2f0ea", fontSize: 19, fontWeight: "800" },
  listFrame: {
    gap: 5,
    padding: 5,
    overflow: "hidden",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.18)",
    backgroundColor: "#15181f",
  },
  lamp: { width: 8, height: 8, marginLeft: 4, borderRadius: 4, backgroundColor: "rgba(255,255,255,0.16)" },
  segment: { flex: 1, flexDirection: "row", gap: 2, padding: 2, borderRadius: 8, backgroundColor: "rgba(0,0,0,0.4)" },
  row: { flexDirection: "row", gap: 5 },
  rowPart: {
    flex: 1,
    minWidth: 0,
    minHeight: 36,
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingVertical: 3,
    paddingHorizontal: 5,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.07)",
    backgroundColor: "rgba(5,7,11,0.62)",
  },
  rowName: { maxWidth: 60, paddingLeft: 3, color: "#f2f0ea", fontSize: 12.5, fontWeight: "800" },
  rowStep: { width: 28, height: 28 },
  rowStepLarge: { width: 64, height: 46, borderRadius: 12 },
  rowPartLarge: { minHeight: 58, gap: 10, padding: 5, borderRadius: 12 },
  thumb: { width: 28, height: 28, borderRadius: 7 },
  rowChoice: {
    flex: 1,
    height: 26,
    borderRadius: 6,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 4,
  },
  rowChoiceText: { color: "#9ba4b4", fontSize: 12, fontWeight: "800" },
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
