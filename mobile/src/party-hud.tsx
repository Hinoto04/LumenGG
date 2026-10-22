import React, { useEffect, useRef, useState } from "react";
import { Image as TileImage } from "expo-image";
import {
  AccessibilityInfo,
  Animated,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  type TextStyle,
} from "react-native";
import { absoluteUrl } from "./api";
import type {
  PartyPlayer,
  PartyState,
  PartyTile,
  PartyRollResult,
} from "./party";
import {
  partyRollNumber,
  partyDieFace,
  partyRollTimes,
  type PartyRollStage,
} from "./party-roll";

const art = (p: PartyPlayer) =>
  absoluteUrl(
    p.character.body_img ||
      p.character.sd_img ||
      p.character.icon_img ||
      p.character.img,
  );
import { PartyCardVisual } from "./party-card";

const ordinals = ["1st", "2nd", "3rd", "4th"];
export function PartyEvent({
  event,
  stage,
}: {
  event: NonNullable<PartyState["event"]>;
  stage: "card" | "effect";
}) {
  const { width } = useWindowDimensions();
  return (
    <View
      pointerEvents="none"
      style={{
        position: "absolute",
        inset: 0,
        zIndex: 30,
        alignItems: "center",
        justifyContent: "center",
        padding: 12,
        backgroundColor: stage === "card" ? "#10283955" : "transparent",
      }}
    >
      {stage === "card" ? (
        <PartyCardVisual card={event} width={Math.min(240, width - 48)} />
      ) : (
        <View
          accessibilityLiveRegion="polite"
          style={{
            padding: 18,
            borderRadius: 20,
            backgroundColor: "#17334bee",
            maxWidth: 360,
          }}
        >
          <Text
            style={{
              fontSize: 26,
              fontWeight: "900",
              color: "#ffe5a4",
              textAlign: "center",
            }}
          >
            {event.label}
          </Text>
          <Text
            style={{
              fontSize: 16,
              lineHeight: 24,
              color: "#fff",
              textAlign: "center",
              marginTop: 10,
            }}
          >
            {event.description}
          </Text>
        </View>
      )}
    </View>
  );
}
export function PartyRoll({
  roll,
  stage,
  name,
  now,
}: {
  roll: PartyRollResult;
  stage: PartyRollStage;
  name: string;
  now: number;
}) {
  const diceVisible = stage === "rolling" || stage === "settled";
  return (
    <View
      pointerEvents="none"
      accessibilityLiveRegion="polite"
      style={hud.roll}
    >
      <Outline
        style={{ fontSize: 11, color: "#fff4c8" }}
      >{`${name}의 주사위`}</Outline>
      {diceVisible ? (
        <View style={hud.rollDice}>
          {roll.dice_values.map((_, i) => (
            <RollingDie
              key={`${roll.version}:${i}`}
              now={now}
              roll={roll}
              index={i}
            />
          ))}
        </View>
      ) : (
        <>
          <View style={{ position: "relative" }}>
            <Outline style={{ fontSize: 80, lineHeight: 88, color: "#fff0ad" }}>
              {String(partyRollNumber(roll, now))}
            </Outline>
            {(stage === "bonus" || stage === "counting") && (
              <View
                style={{
                  position: "absolute",
                  right: -34,
                  top: 0,
                  opacity:
                    stage === "counting"
                      ? Math.max(
                          0,
                          1 -
                            (now - partyRollTimes(roll).count) /
                              Math.max(
                                1,
                                partyRollTimes(roll).total -
                                  partyRollTimes(roll).count,
                              ),
                        )
                      : 1,
                }}
              >
                <Outline
                  style={{ fontSize: 26, color: "#a7ffe4" }}
                >{`+${roll.bonus}`}</Outline>
              </View>
            )}
          </View>
          <Outline style={{ fontSize: 14 }}>칸 이동</Outline>
        </>
      )}
    </View>
  );
}
const pipPositions: Record<number, number[]> = {
  1: [4],
  2: [0, 8],
  3: [0, 4, 8],
  4: [0, 2, 6, 8],
  5: [0, 2, 4, 6, 8],
  6: [0, 2, 3, 5, 6, 8],
};
function RollingDie({
  now,
  roll,
  index,
}: {
  now: number;
  roll: PartyRollResult;
  index: number;
}) {
  const face = partyDieFace(roll, index, now);
  return (
    <View accessibilityLabel={`주사위 ${face}`} style={hud.rollFace}>
      {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((pip) => (
        <View
          key={pip}
          style={{
            width: 8,
            height: 8,
            borderRadius: 4,
            backgroundColor: pipPositions[face]!.includes(pip)
              ? "#253a50"
              : "transparent",
          }}
        />
      ))}
    </View>
  );
}
function Outline({ children, style }: { children: string; style?: TextStyle }) {
  const radius = (style?.fontSize || 14) > 40 ? 2 : 1;
  return (
    <View>
      {[
        [-1, -1],
        [-1, 1],
        [1, -1],
        [1, 1],
      ].map(([x, y], i) => (
        <Text
          key={i}
          accessible={false}
          importantForAccessibility="no"
          numberOfLines={1}
          style={[
            hud.outline,
            style,
            {
              position: "absolute",
              left: x! * radius,
              top: y! * radius,
              color: "#15263e",
            },
          ]}
        >
          {children}
        </Text>
      ))}
      <Text numberOfLines={1} style={[hud.outline, style]}>
        {children}
      </Text>
    </View>
  );
}
function RosterPlayer({
  player,
  index,
  current,
  mine,
  reduced,
  compact,
  onFocus,
}: {
  player: PartyPlayer;
  index: number;
  current: boolean;
  mine: boolean;
  reduced: boolean;
  compact: boolean;
  onFocus: () => void;
}) {
  const rowHeight = compact ? 64 : 80;
  const y = useRef(new Animated.Value(index * rowHeight)).current;
  useEffect(() => {
    if (reduced) {
      y.setValue(index * rowHeight);
      return;
    }
    const animation = Animated.spring(y, {
      toValue: index * rowHeight,
      damping: 22,
      stiffness: 130,
      mass: 1,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [index, reduced, y, rowHeight]);
  return (
    <Animated.View
      style={[
        hud.player,
        {
          height: rowHeight - 2,
          width: compact ? 128 : 145,
          transform: [{ translateY: y }],
        },
      ]}
    >
      <Pressable
        onPress={onFocus}
        accessibilityRole="button"
        accessibilityLabel={`${player.name} 위치 보기`}
        style={{
          width: compact ? 42 : 50,
          height: compact ? 56 : 68,
          alignSelf: "flex-start",
        }}
      >
        <Image
          source={{ uri: art(player) }}
          style={[
            hud.standing,
            compact && { width: 36, height: 54, alignSelf: "center" },
          ]}
          resizeMode="contain"
        />
      </Pressable>
      <View style={hud.playerDetails}>
        <Outline
          style={{
            fontSize: compact ? 9 : 10,
            color: current ? "#ffe599" : "#fff",
          }}
        >{`${current ? "▸ " : ""}${player.name}${mine ? " · 나" : ""}`}</Outline>
        <Outline style={{ color: "#ffe397", fontSize: compact ? 17 : 21 }}>
          {"◆".repeat(Math.min(3, Math.max(0, player.crystals))) +
            "◇".repeat(Math.max(0, 3 - player.crystals)) +
            (player.crystals > 3 ? ` +${player.crystals - 3}` : "")}
        </Outline>
        <View style={hud.stats}>
          <Outline style={{ color: "#ff5269", fontSize: compact ? 12 : 14 }}>
            ♥
          </Outline>
          <Outline style={{ fontSize: compact ? 12 : 14 }}>
            {String(player.hp)}
          </Outline>
          <Outline
            style={{
              color: "#ffdb78",
              marginLeft: 3,
              fontSize: compact ? 12 : 14,
            }}
          >
            ●
          </Outline>
          <Outline style={{ fontSize: compact ? 12 : 14 }}>
            {String(player.coins)}
          </Outline>
        </View>
        <Outline
          style={{ fontSize: compact ? 8 : 9, color: "#a7eaff" }}
        >{`FP ${player.fp}${player.ko_status === "resting" ? " · 휴식" : player.ko_status ? " · 기절" : ""}${player.cloaked ? " · 투명" : ""}${player.shielded ? " · 보호막" : ""}${player.revenge_ready ? " · 반격" : ""}`}</Outline>
      </View>
      <View style={hud.ordinal}>
        <Outline style={{ fontSize: 10, color: current ? "#ffe599" : "#fff" }}>
          {ordinals[index] || ""}
        </Outline>
      </View>
    </Animated.View>
  );
}
export function PartyRoster({
  state,
  onFocusPlayer,
}: {
  state: PartyState;
  onFocusPlayer: (seat: number) => void;
}) {
  const compact = useWindowDimensions().width < 600;
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    let alive = true;
    void AccessibilityInfo.isReduceMotionEnabled().then((value) => {
      if (alive) setReduced(value);
    });
    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      setReduced,
    );
    return () => {
      alive = false;
      subscription.remove();
    };
  }, []);
  const order = state.turn_order || state.players.map((p) => p.seat);
  return (
    <View
      pointerEvents="box-none"
      style={[
        hud.roster,
        {
          width: compact ? 128 : 145,
          height: order.length * (compact ? 64 : 80),
        },
      ]}
    >
      {state.players.map((player) => (
        <RosterPlayer
          key={player.seat}
          player={player}
          index={order.indexOf(player.seat)}
          current={state.status === "running" && player.seat === state.turn}
          mine={player.seat === state.me?.seat}
          reduced={reduced}
          compact={compact}
          onFocus={() => onFocusPlayer(player.seat)}
        />
      ))}
    </View>
  );
}
export function PartyMove({
  disabled,
  onPress,
}: {
  disabled: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="이동"
      disabled={disabled}
      onPress={onPress}
      style={[hud.move, disabled && { opacity: 0.5 }]}
    >
      <Text style={hud.moveText}>이동</Text>
    </Pressable>
  );
}
export function PartySelection({
  tile,
  owner,
  onClose,
}: {
  tile: PartyTile;
  owner?: string;
  onClose: () => void;
}) {
  return (
    <View style={hud.selection}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="칸 정보 닫기"
        onPress={onClose}
        style={hud.close}
      >
        <Text style={{ color: "#fff", fontSize: 25 }}>×</Text>
      </Pressable>
      {!!tile.background_img && (
        <TileImage
          source={{ uri: absoluteUrl(tile.background_img) }}
          style={hud.tileImage}
          contentFit="contain"
        />
      )}
      <Text style={{ color: "#9fe4f5", fontSize: 9 }}>SELECTED</Text>
      <Text
        style={{
          color: "#fff",
          fontSize: 22,
          fontWeight: "900",
          marginBottom: 5,
        }}
      >
        {owner ? `${owner}의 거점` : tile.label}
      </Text>
      <ScrollView nestedScrollEnabled style={{ maxHeight: 160 }}>
        <Text style={{ color: "#fff", fontSize: 16, lineHeight: 24 }}>
          {tile.description}
        </Text>
      </ScrollView>
    </View>
  );
}
export function PartyDuel({
  attacker,
  targets,
  disabled,
  active,
  counter,
  onFight,
  onRelease,
}: {
  attacker: PartyPlayer;
  targets: PartyPlayer[];
  disabled: boolean;
  active?: boolean;
  counter?: boolean;
  onFight: (seat: number) => void;
  onRelease: () => void;
}) {
  const [targetSeat, setTargetSeat] = useState(targets[0]?.seat);
  const opponent = targets.find((p) => p.seat === targetSeat) || targets[0];
  const scale = useRef(new Animated.Value(1.8)).current;
  useEffect(() => {
    let alive = true;
    void AccessibilityInfo.isReduceMotionEnabled().then((reduced) => {
      if (!alive) return;
      if (reduced) scale.setValue(1);
      else
        Animated.spring(scale, {
          toValue: 1,
          useNativeDriver: true,
          damping: 16,
        }).start();
    });
    return () => {
      alive = false;
      scale.stopAnimation();
    };
  }, [scale]);
  if (!opponent) return null;
  return (
    <View style={hud.duel}>
      <Outline style={{ fontSize: 19 }}>
        {active ? "교전 중" : counter ? "반격할까요?" : "승부를 걸까요?"}
      </Outline>
      {targets.length > 1 && (
        <View style={hud.targetChoices}>
          {targets.map((p) => (
            <Pressable
              key={p.seat}
              disabled={disabled}
              onPress={() => setTargetSeat(p.seat)}
              accessibilityRole="button"
              accessibilityState={{ selected: p.seat === opponent.seat }}
              style={[
                hud.target,
                p.seat === opponent.seat && { borderColor: "#ffe397" },
              ]}
            >
              <Text style={{ color: "#fff", fontSize: 11 }}>{p.name}</Text>
            </Pressable>
          ))}
        </View>
      )}
      <View style={hud.cast}>
        {[attacker, opponent].map((p, i) => (
          <React.Fragment key={p.seat}>
            {i === 1 && (
              <Animated.View style={{ transform: [{ scale }] }}>
                <Outline
                  style={{
                    fontSize: 48,
                    color: "#ffe198",
                    fontStyle: "italic",
                  }}
                >
                  VS
                </Outline>
              </Animated.View>
            )}
            <View style={hud.fighter}>
              <Image
                source={{ uri: art(p) }}
                style={hud.fighterImage}
                resizeMode="contain"
              />
              <Outline style={{ fontSize: 13 }}>{p.name}</Outline>
              <Outline
                style={{ fontSize: 12, color: "#ffbec6" }}
              >{`♥${p.hp} · FP ${p.fp}`}</Outline>
            </View>
          </React.Fragment>
        ))}
      </View>
      {!active && (
        <View style={hud.duelActions}>
          <Pressable
            accessibilityRole="button"
            disabled={disabled}
            onPress={onRelease}
            style={[
              hud.duelButton,
              { backgroundColor: "#537ea4" },
              disabled && { opacity: 0.5 },
            ]}
          >
            <Text style={hud.duelButtonText}>놓아주기</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={disabled}
            onPress={() => onFight(opponent.seat)}
            style={[
              hud.duelButton,
              { backgroundColor: "#efb759" },
              disabled && { opacity: 0.5 },
            ]}
          >
            <Text style={[hud.duelButtonText, { color: "#553315" }]}>전투</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}
const hud = StyleSheet.create({
  roll: {
    position: "absolute",
    top: 12,
    alignSelf: "center",
    zIndex: 12,
    width: "85%",
    maxWidth: 360,
    alignItems: "center",
    paddingVertical: 0,
  },
  rollName: {
    fontSize: 13,
    color: "#c5efff",
    fontWeight: "800",
    marginBottom: 8,
  },
  rollDice: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 24,
    height: 105,
  },
  rollFace: {
    width: 58,
    height: 58,
    backgroundColor: "#fff6df",
    borderRadius: 13,
    borderWidth: 2,
    borderColor: "#fff",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 5,
    padding: 9,
    shadowColor: "#172d49",
    shadowOffset: { width: 3, height: 5 },
    shadowOpacity: 0.3,
    shadowRadius: 3,
    elevation: 4,
  },
  rollNumber: {
    fontSize: 39,
    fontWeight: "900",
    color: "#243b54",
    lineHeight: 45,
  },
  rollPlus: { fontSize: 23, color: "#ffe79e", fontWeight: "800" },
  rollCaption: {
    color: "#dbf4ff",
    fontSize: 16,
    marginTop: 10,
    fontWeight: "700",
  },
  rollTotal: {
    color: "#ffe099",
    fontSize: 40,
    fontWeight: "900",
    marginTop: 3,
  },
  outline: { color: "#fff", fontWeight: "900", fontSize: 14 },
  roster: { position: "absolute", left: 3, top: 12, width: 145, zIndex: 3 },
  player: {
    position: "absolute",
    left: 0,
    top: 0,
    width: 145,
    height: 78,
    flexDirection: "row",
    alignItems: "center",
  },
  standing: { width: 50, height: 68, alignSelf: "flex-start" },
  playerDetails: { flex: 1, minWidth: 0 },
  ordinal: { position: "absolute", left: 15, bottom: 0 },
  stats: { flexDirection: "row", alignItems: "center", gap: 1 },
  move: {
    position: "absolute",
    right: 12,
    top: 252,
    width: 96,
    height: 96,
    borderRadius: 28,
    borderWidth: 3,
    borderColor: "#fff0bd",
    backgroundColor: "#f1b855",
    alignItems: "center",
    justifyContent: "center",
    transform: [{ rotate: "-3deg" }],
    zIndex: 4,
  },
  moveText: {
    color: "#553315",
    fontSize: 29,
    fontWeight: "900",
    textAlign: "center",
  },
  selection: {
    position: "absolute",
    top: 60,
    right: 6,
    width: "60%",
    padding: 12,
    paddingTop: 30,
    borderRadius: 16,
    backgroundColor: "#18324bf2",
    borderWidth: 1,
    borderColor: "#ffffff80",
    zIndex: 6,
  },
  close: {
    position: "absolute",
    right: 4,
    top: 0,
    width: 38,
    height: 36,
    alignItems: "center",
  },
  tileImage: { width: 44, height: 44, marginBottom: 4 },
  duel: {
    position: "absolute",
    top: 20,
    left: 0,
    right: 0,
    height: 325,
    padding: 12,
    borderRadius: 20,
    backgroundColor: "#254059ec",
    zIndex: 7,
    alignItems: "center",
  },
  targetChoices: { flexDirection: "row", gap: 5, marginTop: 3 },
  target: {
    borderWidth: 1,
    borderColor: "#6485a3",
    borderRadius: 10,
    padding: 5,
  },
  cast: {
    flex: 1,
    minHeight: 0,
    flexDirection: "row",
    alignItems: "center",
    width: "100%",
  },
  fighter: { flex: 1, minWidth: 0, alignItems: "center", height: "100%" },
  fighterImage: { flex: 1, width: "100%", minHeight: 0 },
  duelActions: { flexDirection: "row", gap: 14, marginTop: 12 },
  duelButton: {
    flex: 1,
    minHeight: 54,
    borderRadius: 17,
    borderWidth: 2,
    borderColor: "#ffffffad",
    justifyContent: "center",
    alignItems: "center",
  },
  duelButtonText: { color: "#fff", fontWeight: "900", fontSize: 23 },
});
