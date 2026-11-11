import React, { useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import type { CalcState } from "./types";
import { calculatorLogRows, type CalculatorLogRow } from "./calculator-log";
import { calculatorTheme } from "./calculator-ui";
import { useApp } from "./provider";

const C = {
  panel: "#141821",
  line: "rgba(255,255,255,0.09)",
  text: "#f2f0ea",
  muted: "#9ba4b4",
  faint: "#687183",
  plus: "#4fdc86",
  minus: "#ff6470",
};

/**
 * 기록: 시뮬레이터(대전 클라이언트) 기록과 같은 모양의 오른쪽 패널.
 * 최신이 위, 플레이어별 테마 색 배경, 오른쪽에 증감치, 전체 사건은 구분선.
 */
export function CalculatorHistoryPanel({
  state,
  visible,
  onClose,
}: {
  state: CalcState | null;
  visible: boolean;
  onClose: () => void;
}) {
  const { t } = useApp();
  const [filter, setFilter] = useState<"all" | "p1" | "p2">("all");
  const rows = state ? calculatorLogRows(state, t) : [];
  const shown = rows.filter((row) => filter === "all" || row.target === filter);
  const color = (target: "p1" | "p2") =>
    calculatorTheme(state?.players[target]?.character).accent ||
    (target === "p1" ? "#45d0a0" : "#b892ff");
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      supportedOrientations={["landscape", "landscape-left", "landscape-right", "portrait"]}
    >
      <View style={s.backdrop}>
        <Pressable style={StyleSheet.absoluteFill} accessibilityRole="button" accessibilityLabel={t("닫기")} onPress={onClose} />
        <SafeAreaView edges={["top", "bottom", "right"]} style={s.panelWrap} pointerEvents="box-none">
          <View style={s.panel}>
            <View style={s.head}>
              <Text accessibilityRole="header" style={s.title}>
                {t("기록")}
              </Text>
              <Pressable accessibilityRole="button" onPress={onClose} style={s.close}>
                <Text style={s.closeText}>{t("닫기")}</Text>
              </Pressable>
            </View>
            <View style={s.filters}>
              {(["all", "p1", "p2"] as const).map((key) => (
                <Pressable
                  key={key}
                  accessibilityRole="button"
                  accessibilityState={{ selected: filter === key }}
                  onPress={() => setFilter(key)}
                  style={[s.filter, filter === key && s.filterOn]}
                >
                  {key !== "all" && <View style={[s.dot, { backgroundColor: color(key) }]} />}
                  <Text numberOfLines={1} style={[s.filterText, filter === key && { color: C.text }]}>
                    {key === "all" ? t("전체") : state?.players[key]?.name || t(key === "p1" ? "플레이어1" : "플레이어2")}
                  </Text>
                </Pressable>
              ))}
            </View>
            <ScrollView contentContainerStyle={s.list}>
              {!shown.length && <Text style={s.empty}>{t("표시할 기록이 없습니다.")}</Text>}
              {shown.map((row) => (
                <Row key={row.id} row={row} tint={row.target ? color(row.target) : ""} name={row.target ? state?.players[row.target]?.name || "" : ""} />
              ))}
            </ScrollView>
          </View>
        </SafeAreaView>
      </View>
    </Modal>
  );
}

function Row({ row, tint, name }: { row: CalculatorLogRow; tint: string; name: string }) {
  const { t } = useApp();
  if (!row.target)
    return (
      <View style={[s.divider, row.undone && { opacity: 0.45 }]} accessible accessibilityLabel={`${row.title} ${row.detail}`}>
        <View style={s.rule} />
        <Text style={s.dividerText}>{[row.title, row.detail].filter(Boolean).join(" · ")}</Text>
        <View style={s.rule} />
      </View>
    );
  const meta = [name, row.detail, row.time].filter(Boolean).join(" · ");
  const delta = row.delta;
  return (
    <View
      accessible
      accessibilityLabel={`${name}, ${row.title}, ${row.detail}${row.undone ? `, ${t("되돌림")}` : ""}`}
      style={[s.row, { backgroundColor: tint + "24", borderLeftColor: tint }, row.undone && { opacity: 0.45 }]}
    >
      <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
        <Text style={[s.rowTitle, row.undone && s.strike]}>
          {row.title}
          {row.undone ? ` · ${t("되돌림")}` : ""}
        </Text>
        <Text style={s.meta}>{meta}</Text>
      </View>
      {!!delta && (
        <Text style={[s.delta, { color: delta.amount > 0 ? C.plus : C.minus }, row.undone && s.strike]}>
          {`${delta.label} ${delta.amount > 0 ? "+" : "−"}${Math.abs(delta.amount)}`.trim()}
        </Text>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(8,8,8,0.5)" },
  panelWrap: { flex: 1, alignItems: "flex-end" },
  panel: {
    flex: 1,
    width: 400,
    maxWidth: "92%",
    margin: 8,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: C.line,
    backgroundColor: C.panel,
    overflow: "hidden",
  },
  head: { flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderColor: C.line },
  title: { flex: 1, color: C.text, fontSize: 17, fontWeight: "800" },
  close: { minHeight: 36, paddingHorizontal: 14, borderRadius: 999, borderWidth: 1, borderColor: C.line, justifyContent: "center" },
  closeText: { color: C.text, fontSize: 13, fontWeight: "700" },
  filters: { flexDirection: "row", gap: 6, paddingHorizontal: 10, paddingVertical: 8, borderBottomWidth: 1, borderColor: C.line },
  filter: {
    flexShrink: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    minHeight: 32,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: C.line,
  },
  filterOn: { backgroundColor: "rgba(255,255,255,0.1)", borderColor: "rgba(255,255,255,0.18)" },
  filterText: { color: C.muted, fontSize: 12.5, fontWeight: "700", flexShrink: 1 },
  dot: { width: 10, height: 10, borderRadius: 3 },
  list: { padding: 8, gap: 5 },
  empty: { color: C.faint, fontSize: 12, textAlign: "center", padding: 20 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: 9,
    borderLeftWidth: 3,
  },
  rowTitle: { color: C.text, fontSize: 14, fontWeight: "700" },
  meta: { color: C.muted, fontSize: 11.5, fontVariant: ["tabular-nums"] },
  delta: { fontSize: 14, fontWeight: "900", fontVariant: ["tabular-nums"] },
  strike: { textDecorationLine: "line-through" },
  divider: { flexDirection: "row", alignItems: "center", gap: 8, marginVertical: 4 },
  rule: { flex: 1, height: 1, backgroundColor: C.line },
  dividerText: { color: C.muted, fontSize: 11.5 },
});
