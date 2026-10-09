import React from "react";
import { StyleSheet, Text, View } from "react-native";
import type { CalcState } from "./types";
import { calculatorLogRows } from "./calculator-log";
import { useApp } from "./provider";
import { colors, Notice } from "./ui";

export function CalculatorHistory({ state }: { state: CalcState | null }) {
  const { t } = useApp();
  const rows = state ? calculatorLogRows(state, t) : [];
  return (
    <View style={{ gap: 10 }}>
      {!rows.length && <Notice text="기록이 없습니다." />}
      {rows.map((row) => (
        <View
          key={row.id}
          accessibilityLabel={`${row.player}, ${row.title}, ${row.detail}${row.undone ? `, ${t("되돌림")}` : ""}`}
          style={[
            history.row,
            row.target === "p1"
              ? history.p1
              : row.target === "p2"
                ? history.p2
                : history.global,
            row.undone && { opacity: 0.55 },
          ]}
        >
          <View style={history.heading}>
            <Text
              style={[
                history.player,
                {
                  color:
                    row.target === "p1"
                      ? "#72cbbf"
                      : row.target === "p2"
                        ? colors.accent
                        : colors.muted,
                },
              ]}
            >
              {row.player}
            </Text>
            <Text style={history.time}>{row.time}</Text>
          </View>
          <Text style={history.title}>
            {row.title}
            {row.undone ? ` · ${t("되돌림")}` : ""}
          </Text>
          {!!row.detail && <Text style={history.detail}>{row.detail}</Text>}
        </View>
      ))}
    </View>
  );
}
const history = StyleSheet.create({
  row: { width: "86%", borderRadius: 12, borderWidth: 1, padding: 12 },
  p1: {
    alignSelf: "flex-start",
    backgroundColor: "#172f2c",
    borderColor: "#38685f",
    borderLeftWidth: 4,
  },
  p2: {
    alignSelf: "flex-end",
    backgroundColor: "#342a18",
    borderColor: "#806838",
    borderRightWidth: 4,
  },
  global: {
    alignSelf: "center",
    backgroundColor: colors.panel,
    borderColor: colors.line,
  },
  heading: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  player: { fontSize: 13, fontWeight: "700", flex: 1 },
  time: { color: colors.muted, fontSize: 11 },
  title: { color: colors.text, fontSize: 16, fontWeight: "700", marginTop: 7 },
  detail: { color: colors.text, fontSize: 17, marginTop: 5 },
});
