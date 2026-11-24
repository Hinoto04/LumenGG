import React, { useEffect, useState } from "react";
import { Image, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions } from "react-native";
import type { Character } from "./types";
import { CharacterIconImage, characterFace } from "./character-picker";
import { CachedImage, colors } from "./ui";
import { cachedImage } from "./catalog";
import { absoluteUrl } from "./api";
import { useApp } from "./provider";
import { localized } from "./core";

type Side = "p1" | "p2";
const SIDE_COLOR: Record<Side, string> = { p1: "#5bbeb0", p2: "#b989d6" };
const GOLD = "#e0b45b";
const CARD_RATIO = 1117 / 821;
/** 패시브 카드 가운데 일러스트(가로 20~80%, 위 12%부터)를 정사각형으로 잘라 아이콘처럼 쓴다. */
const TRAIT_ICON = { x: 0.2, y: 0.12, w: 0.6 };

function useLocalImage(url: string) {
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

function TraitIcon({ url, size }: { url: string; size: number }) {
  const source = useLocalImage(url);
  const width = size / TRAIT_ICON.w;
  const height = width * CARD_RATIO;
  return (
    <View style={{ width: size, height: size, overflow: "hidden", borderRadius: 7, backgroundColor: colors.surface2 }}>
      {!!source && (
        <Image source={{ uri: source }} style={{ position: "absolute", width, height, left: -TRAIT_ICON.x * width, top: -TRAIT_ICON.y * height }} />
      )}
    </View>
  );
}

/**
 * 계산기 시작 전 격투게임식 선택 화면(웹 calculator-select.js와 같은 흐름).
 * 넓으면 [1P | 로스터 | 2P], 좁으면 [1P | 2P] 아래 로스터. 로스터를 누르면 지금 고르는 쪽에 들어가고,
 * 상대가 아직 고르지 않았으면 그쪽으로 넘어간다. 패시브(특성)는 카드 그림으로 고른다.
 */
export function FighterSelect({
  characters,
  value,
  traits,
  onCharacter,
  onTrait,
}: {
  characters: Character[];
  value: Record<Side, string>;
  traits: Record<Side, string>;
  onCharacter: (side: Side, id: string) => void;
  onTrait: (side: Side, id: string) => void;
}) {
  const { language, t } = useApp();
  const [active, setActive] = useState<Side>("p1");
  const [touched, setTouched] = useState<Record<Side, boolean>>({ p1: false, p2: false });
  const [width, setWidth] = useState(0);
  const screen = useWindowDimensions();
  const wide = width >= 620;
  const byId = (id: string) => characters.find((c) => String(c.id) === id);

  const pick = (id: string) => {
    onCharacter(active, id);
    const character = byId(id);
    // 패시브가 하나뿐이면 바로 고른다.
    onTrait(active, character?.traits?.length === 1 ? String(character.traits[0]!.id) : "");
    const next = { ...touched, [active]: true };
    setTouched(next);
    const other: Side = active === "p1" ? "p2" : "p1";
    if (!next[other]) setActive(other);
  };

  const fighter = (side: Side) => {
    const character = byId(value[side]);
    const color = SIDE_COLOR[side];
    const selected = active === side;
    const name = character ? localized(character, language) : t("캐릭터를 고르세요");
    return (
      <Pressable
        key={side}
        accessibilityRole="button"
        accessibilityLabel={`${side === "p1" ? "1P" : "2P"} · ${name}`}
        accessibilityState={{ selected }}
        onPress={() => setActive(side)}
        style={[
          s.fighter,
          { borderColor: selected ? color : "rgba(255,255,255,0.12)" },
          selected && { shadowColor: color, shadowOpacity: 0.6, shadowRadius: 12, elevation: 4 },
          wide ? { width: Math.min(220, width * 0.27) } : { flex: 1 },
        ]}
      >
        <View style={s.fighterHead}>
          <Text style={[s.tag, { backgroundColor: color }]}>{side === "p1" ? "1P" : "2P"}</Text>
          {selected && <Text style={[s.picking, { color }]}>{t("선택 중")}</Text>}
        </View>
        <View style={[s.portrait, { height: wide ? 200 : 150 }]}>
          {character?.img ? (
            <View style={[StyleSheet.absoluteFill, side === "p2" && { transform: [{ scaleX: -1 }] }]}>
              <CachedImage key={character.img} url={character.img} large fill transparent height="100%" />
            </View>
          ) : (
            <Text style={s.empty}>?</Text>
          )}
          <View style={s.nameShade}>
            <Text numberOfLines={1} adjustsFontSizeToFit style={s.name}>
              {name}
            </Text>
          </View>
        </View>
        {!!character?.traits?.length && (
          <View accessibilityRole="radiogroup" accessibilityLabel={t("패시브 선택")} style={s.traits}>
            {character.traits.map((trait) => {
              const on = traits[side] === String(trait.id);
              const label = localized(trait, language) || trait.name;
              return (
                <Pressable
                  key={trait.id}
                  accessibilityRole="radio"
                  accessibilityLabel={label}
                  accessibilityState={{ checked: on }}
                  onPress={() => onTrait(side, String(trait.id))}
                  style={({ pressed }) => [s.trait, on && s.traitOn, pressed && { transform: [{ scale: 0.97 }] }]}
                >
                  <View style={{ opacity: on ? 1 : 0.55 }}>
                    {!!trait.img && <TraitIcon url={trait.img} size={48} />}
                  </View>
                  <Text numberOfLines={1} style={[s.traitName, on && { color: colors.text }]}>
                    {label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        )}
      </Pressable>
    );
  };

  // 화면 높이에 맞춰 로스터 칸 크기를 정한다(로스터가 화면 높이의 40% 안에 들어오게).
  const columns = Math.max(4, Math.floor((wide ? width * 0.42 : width) / 70));
  const rows = Math.ceil(characters.length / columns);
  const byHeight = (screen.height * 0.4 - 6 * (rows - 1)) / rows - 18;
  const cell = Math.round(Math.max(40, Math.min(wide ? 64 : 68, byHeight)));
  const roster = (
    <View accessibilityRole="radiogroup" accessibilityLabel={t("캐릭터 선택")} style={[s.roster, wide ? { flex: 1 } : null]}>
      {characters.map((character) => {
        const id = String(character.id);
        const p1 = value.p1 === id && touched.p1;
        const p2 = value.p2 === id && touched.p2;
        const border = p1 && p2 ? GOLD : p1 ? SIDE_COLOR.p1 : p2 ? SIDE_COLOR.p2 : "rgba(255,255,255,0.12)";
        return (
          <Pressable
            key={id}
            accessibilityRole="radio"
            accessibilityLabel={localized(character, language)}
            accessibilityState={{ checked: p1 || p2 }}
            onPress={() => pick(id)}
            style={({ pressed }) => [s.cell, { width: cell + 4, borderColor: border }, pressed && { transform: [{ scale: 0.95 }] }]}
          >
            {/* 캐릭터 아이콘은 시계방향 45도로 기울여 쓰도록 그려져 있다. 칸 안에서만 돌린다. */}
            <View style={{ width: cell, height: cell, overflow: "hidden", borderRadius: 7, backgroundColor: character.color ? character.color + "40" : colors.surface2 }}>
              <CharacterIconImage {...characterFace(character)} width={cell} height={cell} />
            </View>
            <Text numberOfLines={1} style={s.cellName}>
              {localized(character, language)}
            </Text>
            {p1 && <Text style={[s.badge, { left: 2, backgroundColor: SIDE_COLOR.p1 }]}>1P</Text>}
            {p2 && <Text style={[s.badge, { right: 2, backgroundColor: SIDE_COLOR.p2 }]}>2P</Text>}
          </Pressable>
        );
      })}
    </View>
  );

  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)} style={{ gap: 10, marginBottom: 16 }}>
      {width > 0 &&
        (wide ? (
          <View style={s.wideRow}>
            {fighter("p1")}
            <ScrollView style={{ flex: 1, maxHeight: 340 }} contentContainerStyle={{ paddingVertical: 2 }}>
              {roster}
            </ScrollView>
            {fighter("p2")}
          </View>
        ) : (
          <>
            <View style={s.narrowRow}>
              {fighter("p1")}
              {fighter("p2")}
            </View>
            {roster}
          </>
        ))}
    </View>
  );
}

const s = StyleSheet.create({
  wideRow: { flexDirection: "row", gap: 10, alignItems: "stretch" },
  narrowRow: { flexDirection: "row", gap: 8 },
  fighter: {
    gap: 8,
    padding: 8,
    borderRadius: 16,
    borderWidth: 1.5,
    backgroundColor: "rgba(255,255,255,0.03)",
  },
  fighterHead: { flexDirection: "row", alignItems: "center", gap: 8 },
  tag: {
    paddingHorizontal: 9,
    paddingVertical: 2,
    borderRadius: 7,
    overflow: "hidden",
    color: "#111",
    fontSize: 14,
    fontWeight: "900",
    fontStyle: "italic",
  },
  picking: { fontSize: 12, fontWeight: "800" },
  portrait: { overflow: "hidden", borderRadius: 12, backgroundColor: "rgba(0,0,0,0.25)", justifyContent: "flex-end" },
  empty: { position: "absolute", alignSelf: "center", top: "30%", color: "rgba(255,255,255,0.18)", fontSize: 56, fontWeight: "900" },
  nameShade: { paddingTop: 16, paddingBottom: 6, paddingHorizontal: 6, backgroundColor: "rgba(0,0,0,0.55)" },
  name: { color: "#fff", fontSize: 18, fontWeight: "900", textAlign: "center" },
  traits: { flexDirection: "row", gap: 6 },
  trait: {
    alignItems: "center",
    width: 58,
    gap: 3,
    padding: 3,
    borderRadius: 9,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.12)",
    backgroundColor: colors.surface2,
  },
  traitOn: { borderColor: GOLD, borderWidth: 2 },
  traitName: { color: colors.muted, fontSize: 11, fontWeight: "800", textAlign: "center" },
  roster: { flexDirection: "row", flexWrap: "wrap", gap: 6, justifyContent: "center" },
  cell: {
    alignItems: "center",
    gap: 2,
    paddingTop: 0,
    paddingBottom: 2,
    overflow: "hidden",
    borderRadius: 10,
    borderWidth: 2,
    backgroundColor: colors.surface2,
  },
  cellName: { maxWidth: "100%", paddingHorizontal: 2, color: colors.text, fontSize: 11, fontWeight: "700" },
  badge: {
    position: "absolute",
    top: 2,
    paddingHorizontal: 4,
    borderRadius: 5,
    overflow: "hidden",
    color: "#111",
    fontSize: 9,
    fontWeight: "900",
    fontStyle: "italic",
  },
});
