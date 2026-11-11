import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { Icon, colors, styles, type IconName } from "./ui";

/** 대회 진행 상태별 배지 색. */
export function statusTone(status: string): "accent" | "success" | "neutral" {
  return status === "running"
    ? "accent"
    : status === "registration"
      ? "success"
      : "neutral";
}

/** 아이콘이 붙은 한 줄 정보(일시·장소·참가자명 등). */
export function InfoLine({ icon, text }: { icon: IconName; text: string }) {
  return (
    <View style={infoStyles.line}>
      <Icon name={icon} size={14} color={colors.subtle} />
      <Text style={[styles.muted, { flex: 1 }]} numberOfLines={1}>
        {text}
      </Text>
    </View>
  );
}

const infoStyles = StyleSheet.create({
  line: { flexDirection: "row", alignItems: "center", gap: 6 },
});
