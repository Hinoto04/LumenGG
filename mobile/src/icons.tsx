import React from "react";
import { StyleSheet, View } from "react-native";
import { colors } from "./ui";

export function ListIcon({ kind }: { kind: "sort" | "grid" | "detail" }) {
  return (
    <View
      accessible={false}
      importantForAccessibility="no"
      style={icons.canvas}
    >
      {kind === "grid" ? (
        <View style={icons.grid}>
          {[0, 1, 2, 3].map((i) => (
            <View key={i} style={icons.square} />
          ))}
        </View>
      ) : kind === "detail" ? (
        <View style={icons.lines}>
          {[0, 1, 2].map((i) => (
            <View key={i} style={icons.row}>
              <View style={icons.bullet} />
              <View style={icons.line} />
            </View>
          ))}
        </View>
      ) : (
        <View style={icons.row}>
          <View style={icons.lines}>
            {[15, 11, 7].map((width) => (
              <View key={width} style={[icons.line, { width }]} />
            ))}
          </View>
          <View style={icons.arrow}>
            <View style={icons.stem} />
            <View style={icons.arrowhead} />
          </View>
        </View>
      )}
    </View>
  );
}
const icons = StyleSheet.create({
  canvas: {
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  grid: { width: 21, flexDirection: "row", flexWrap: "wrap", gap: 3 },
  square: {
    width: 9,
    height: 9,
    borderWidth: 1.6,
    borderColor: colors.accent,
    borderRadius: 1,
  },
  lines: { gap: 5 },
  row: { flexDirection: "row", alignItems: "center", gap: 3 },
  bullet: { width: 4, height: 4, borderWidth: 1, borderColor: colors.accent },
  line: {
    width: 14,
    height: 2,
    borderRadius: 1,
    backgroundColor: colors.accent,
  },
  arrow: { width: 7, height: 19, alignItems: "center" },
  stem: { width: 2, height: 16, backgroundColor: colors.accent },
  arrowhead: {
    position: "absolute",
    bottom: 1,
    width: 7,
    height: 7,
    borderRightWidth: 2,
    borderBottomWidth: 2,
    borderColor: colors.accent,
    transform: [{ rotate: "45deg" }],
  },
});
