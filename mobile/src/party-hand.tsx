import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Animated,
  PanResponder,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  type GestureResponderEvent,
  type PanResponderGestureState,
} from "react-native";
import { PartyCardVisual } from "./party-card";
import type { PartyItem, PartyState } from "./party";

export function PartyHand({
  state,
  disabled,
  boardRef,
  onChoose,
  onUse,
  onDragging,
}: {
  state: PartyState;
  disabled: boolean;
  boardRef: React.RefObject<View | null>;
  onChoose: (item: string) => void;
  onUse: (item: string) => void;
  onDragging: (dragging: boolean) => void;
}) {
  const [raised, setRaised] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const { width } = useWindowDimensions();
  const cardWidth = Math.min(180, width * 0.4),
    cardHeight = (cardWidth * 88) / 63;
  const identity = `${state.code}:${state.me?.seat}:${state.me?.items.join(",")}`;
  useEffect(() => {
    setRaised(null);
    setDragging(false);
    onDragging(false);
  }, [identity]);
  useEffect(() => () => onDragging(false), []);
  function drag(value: boolean) {
    setDragging(value);
    onDragging(value);
  }
  return (
    <View pointerEvents="box-none" style={s.overlay}>
      {dragging && (
        <View pointerEvents="none" style={s.drop}>
          <Text style={s.dropText}>
            {disabled
              ? "아이템은 내 턴의 이동 전에 사용해요"
              : "여기에 놓아 사용"}
          </Text>
        </View>
      )}
      <View
        pointerEvents="box-none"
        style={[s.hand, { bottom: (-cardHeight * 2) / 3 }]}
      >
        {[0, 1, 2].map((index) => {
          const key = state.me?.items[index],
            item = key ? state.board.shop[key] : null;
          return (
            <HandCard
              key={`${identity}:${index}`}
              item={item || null}
              width={cardWidth}
              raised={raised === index}
              disabled={disabled}
              boardRef={boardRef}
              onTap={() => {
                if (raised === index && key) onChoose(key);
                else setRaised(index);
              }}
              onUse={() => {
                setRaised(null);
                if (key) onUse(key);
              }}
              onDragging={drag}
              overlap={index > 0}
            />
          );
        })}
      </View>
    </View>
  );
}

function HandCard({
  item,
  width,
  raised,
  disabled,
  boardRef,
  onTap,
  onUse,
  onDragging,
  overlap,
}: {
  item: PartyItem | null;
  width: number;
  raised: boolean;
  disabled: boolean;
  overlap: boolean;
  boardRef: React.RefObject<View | null>;
  onTap: () => void;
  onUse: () => void;
  onDragging: (value: boolean) => void;
}) {
  const xy = useRef(new Animated.ValueXY()).current;
  const moving = useRef(false);
  const bounds = useRef<{
    x: number;
    y: number;
    width: number;
    height: number;
  } | null>(null);
  const [dragging, setDragging] = useState(false);
  const latest = useRef({ disabled, onTap, onUse, onDragging, boardRef });
  latest.current = { disabled, onTap, onUse, onDragging, boardRef };
  const responder = useMemo(() => {
    function finish(cancelled: boolean, gesture?: PanResponderGestureState) {
      const wasMoving = moving.current,
        r = bounds.current;
      moving.current = false;
      setDragging(false);
      latest.current.onDragging(false);
      Animated.spring(xy, {
        toValue: { x: 0, y: 0 },
        useNativeDriver: true,
      }).start();
      if (cancelled) return;
      if (!wasMoving) {
        latest.current.onTap();
        return;
      }
      if (
        !latest.current.disabled &&
        r &&
        gesture &&
        gesture.moveX >= r.x + r.width * 0.2 &&
        gesture.moveX <= r.x + r.width * 0.8 &&
        gesture.moveY >= r.y + r.height * 0.25 &&
        gesture.moveY <= r.y + r.height * 0.7
      )
        latest.current.onUse();
    }
    return PanResponder.create({
      onStartShouldSetPanResponder: () => !!item,
      onMoveShouldSetPanResponder: () => !!item,
      onPanResponderGrant: () => {
        moving.current = false;
        bounds.current = null;
        xy.stopAnimation();
        xy.setValue({ x: 0, y: 0 });
        latest.current.boardRef.current?.measureInWindow(
          (x, y, width, height) => {
            bounds.current = { x, y, width, height };
          },
        );
      },
      onPanResponderMove: (
        _event: GestureResponderEvent,
        gesture: PanResponderGestureState,
      ) => {
        if (!moving.current && Math.hypot(gesture.dx, gesture.dy) > 8) {
          moving.current = true;
          setDragging(true);
          latest.current.onDragging(true);
        }
        if (moving.current) xy.setValue({ x: gesture.dx, y: gesture.dy });
      },
      onPanResponderRelease: (_event, gesture) => finish(false, gesture),
      onPanResponderTerminate: () => finish(true),
      onPanResponderTerminationRequest: () => false,
    });
  }, [!!item]);
  const height = (width * 88) / 63;
  return (
    <Animated.View
      {...responder.panHandlers}
      accessible
      accessibilityRole="button"
      accessibilityLabel={
        item
          ? `${item.label} · 눌러서 펼치기 · 중앙으로 끌어 사용`
          : "빈 아이템 칸"
      }
      accessibilityActions={[{ name: "activate", label: "카드 보기" }]}
      onAccessibilityAction={() => item && latest.current.onTap()}
      style={[
        s.card,
        {
          width,
          height,
          marginLeft: overlap ? -width * 0.4 : 0,
          zIndex: dragging ? 20 : raised ? 10 : 1,
          transform: [
            { translateX: xy.x },
            {
              translateY: Animated.add(
                xy.y,
                raised ? (-height * 2) / 3 - 16 : 0,
              ),
            },
          ],
        },
        !item && s.empty,
      ]}
    >
      {item && <PartyCardVisual card={item} width={width} compact />}
    </Animated.View>
  );
}

const s = StyleSheet.create({
  overlay: { position: "absolute", inset: 0, zIndex: 15 },
  hand: { position: "absolute", alignSelf: "center", flexDirection: "row" },
  card: {
    borderRadius: 12,
    shadowColor: "#000",
    shadowOpacity: 0.3,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: -4 },
    elevation: 12,
  },
  empty: {
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: "#ffffff55",
    backgroundColor: "#284b6333",
  },
  drop: {
    position: "absolute",
    left: "20%",
    right: "20%",
    top: "25%",
    bottom: "30%",
    borderWidth: 3,
    borderStyle: "dashed",
    borderColor: "#fff0b3",
    backgroundColor: "#143348bf",
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
  },
  dropText: {
    color: "white",
    fontSize: 23,
    fontWeight: "900",
    textAlign: "center",
  },
});
