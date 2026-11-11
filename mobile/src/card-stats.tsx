import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useApp } from "./provider";
import { colors, radius, space } from "./ui";
import type { Card } from "./types";

const empty = (value: string | number | null | undefined) =>
  value === null || value === undefined || value === "" ? "—" : String(value);

/** 카드 수치(속도·대미지·Hit·Guard·Counter)를 같은 폭의 칸으로 보여 준다. */
export function CardStats({
  card,
  compact = false,
}: {
  card: Card;
  compact?: boolean;
}) {
  const { t } = useApp();
  const stats = [
    { label: t("속도"), value: empty(card.frame) },
    { label: t("대미지"), value: empty(card.damage) },
    { label: "Hit", value: empty(card.hit) },
    { label: "Guard", value: empty(card.guard) },
    { label: "Counter", value: empty(card.counter) },
  ];
  const guards = card.type.includes("수비")
    ? [
        { label: t("상단"), value: empty(card.g_top) },
        { label: t("중단"), value: empty(card.g_mid) },
        { label: t("하단"), value: empty(card.g_bot) },
      ]
    : [];
  return (
    <View style={{ gap: compact ? 4 : space.sm }}>
      <StatRow items={stats} compact={compact} />
      {guards.length > 0 && <StatRow items={guards} compact={compact} />}
    </View>
  );
}

function StatRow({
  items,
  compact,
}: {
  items: { label: string; value: string }[];
  compact: boolean;
}) {
  return (
    <View style={[statStyles.row, compact && statStyles.compactRow]}>
      {items.map((item) => (
        <View
          key={item.label}
          accessible
          accessibilityLabel={`${item.label} ${item.value}`}
          style={[statStyles.cell, compact && statStyles.compactCell]}
        >
          <Text
            numberOfLines={1}
            adjustsFontSizeToFit
            style={[statStyles.value, compact && statStyles.compactValue]}
          >
            {item.value}
          </Text>
          <Text
            numberOfLines={1}
            style={[statStyles.label, compact && statStyles.compactLabel]}
          >
            {item.label}
          </Text>
        </View>
      ))}
    </View>
  );
}

const statStyles = StyleSheet.create({
  row: { flexDirection: "row", gap: space.sm },
  compactRow: { gap: 4 },
  cell: {
    flex: 1,
    alignItems: "center",
    paddingVertical: space.sm + 2,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
  },
  compactCell: { paddingVertical: 5, borderRadius: radius.sm },
  value: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "700",
    fontVariant: ["tabular-nums"],
  },
  compactValue: { fontSize: 14 },
  label: { color: colors.muted, fontSize: 11, marginTop: 2 },
  compactLabel: { fontSize: 10, marginTop: 0 },
});
