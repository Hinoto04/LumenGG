import React, { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import type { AmbientEffect } from "./calculator-visual-model";

/** State decoration only: never sends actions, captures touches, or replays a trigger. */
export function PassiveAura({
  active,
  allowed,
  kind = "light",
  color,
}: {
  active: boolean;
  allowed: boolean;
  kind?: AmbientEffect;
  color: string;
}) {
  const progress = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    progress.stopAnimation();
    progress.setValue(0);
    if (!active || !allowed) return;
    const loop = Animated.loop(
      Animated.timing(progress, {
        toValue: 1,
        duration:
          kind === "arc"
            ? 3300
            : kind === "orbit"
              ? 6000
              : kind === "fire"
                ? 2200
                : 3500,
        useNativeDriver: true,
        isInteraction: false,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [active, allowed, kind, progress]);
  if (!active) return null;
  const opacity = progress.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0.16, 0.34, 0.16],
  });
  const turn = progress.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });
  const rise = progress.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0, -7, 0],
  });
  const sway = progress.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: ["-6deg", "8deg", "-6deg"],
  });
  const scale = progress.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0.95, 1.05, 0.95],
  });
  return (
    <View
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={[StyleSheet.absoluteFill, { overflow: "hidden", borderRadius: 10 }]}
    >
      {kind === "arc" || kind === "orbit" ? (
        <>
          <Animated.View
            style={[
              styles.ring,
              {
                borderTopColor: color,
                borderBottomColor: color,
                opacity: allowed ? 0.35 : 0.16,
                transform: allowed ? [{ rotate: turn }] : [],
              },
            ]}
          />
          <Animated.View
            style={[
              styles.innerRing,
              {
                borderRightColor: color,
                opacity: 0.2,
                transform: allowed ? [{ rotate: turn }] : [],
              },
            ]}
          />
        </>
      ) : kind === "fire" ? (
        [0, 1, 2].map((i) => (
          <Animated.View
            key={i}
            style={{
              position: "absolute",
              left: ([17, 43, 70][i] + "%") as `${number}%`,
              bottom: "9%",
              width: "17%",
              height: i === 1 ? "58%" : "40%",
              borderRadius: 25,
              backgroundColor: color,
              opacity: allowed ? opacity : 0.14,
              transform: allowed
                ? [{ translateY: rise }, { rotate: sway }, { scaleY: scale }]
                : [],
            }}
          />
        ))
      ) : kind === "spark" ? (
        [0, 1, 2].map((i) => (
          <Animated.View
            key={i}
            style={{
              position: "absolute",
              left: ([16, 78, 55][i] + "%") as `${number}%`,
              top: ([64, 30, 12][i] + "%") as `${number}%`,
              width: 4,
              height: 4,
              backgroundColor: color,
              opacity: allowed ? opacity : 0.2,
              transform: allowed
                ? [{ translateY: rise }, { rotate: turn }]
                : [{ rotate: "45deg" }],
            }}
          />
        ))
      ) : kind === "wave" ? (
        [0, 1, 2].map((i) => (
          <Animated.View
            key={i}
            style={[
              styles.ring,
              {
                inset: 4 + i * 7,
                borderColor: [color, "#f799da", "#ffe592"][i],
                borderWidth: 1,
                opacity: allowed ? opacity : 0.12,
                transform: allowed ? [{ scale }] : [],
              },
            ]}
          />
        ))
      ) : (
        <Animated.View
          style={[
            StyleSheet.absoluteFill,
            {
              borderRadius: kind === "mist" ? 40 : 10,
              borderWidth: kind === "light" ? 1 : 0,
              borderColor: color,
              backgroundColor: kind === "mist" ? color : "transparent",
              opacity: allowed ? opacity : 0.12,
              transform: allowed
                ? [{ translateY: kind === "mist" ? rise : 0 }, { scale }]
                : [],
            },
          ]}
        />
      )}
    </View>
  );
}
const styles = StyleSheet.create({
  ring: {
    position: "absolute",
    inset: 2,
    borderRadius: 100,
    borderWidth: 2,
    borderColor: "transparent",
  },
  innerRing: {
    position: "absolute",
    inset: 10,
    borderRadius: 100,
    borderWidth: 1,
    borderColor: "transparent",
  },
});
