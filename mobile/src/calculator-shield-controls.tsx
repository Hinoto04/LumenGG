import React from "react";
import { View, Text, Pressable } from "react-native";
import type { Action, Player } from "./types";
import { supportsShield } from "./calculator-shield";
import { useApp } from "./provider";

export function ShieldPassiveRow({
  player,
  target,
  disabled,
  pending,
  onShield,
  onAction,
  children,
}: {
  player: Player;
  target: "p1" | "p2";
  disabled: boolean;
  pending: number;
  onShield: (amount: number) => void;
  onAction: (a: Action) => Promise<void>;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  if (!supportsShield(player)) return <>{children}</>;
  const label = t(target === "p1" ? "플레이어1" : "플레이어2");
  return (
    <View
      style={{
        flex: 1,
        minHeight: 0,
        flexDirection: "row",
        gap: 8,
        alignItems: "stretch",
      }}
    >
      <View style={{ flex: 1, minWidth: 0 }}>{children}</View>
      <View style={{ width: 76, gap: 4, justifyContent: "center" }}>
        {[100, 0, -100].map((step) => (
          <Pressable
            key={step}
            accessibilityRole="button"
            accessibilityLabel={`${label} ${t("보호막")} ${step ? (step > 0 ? "+100" : "-100") : t("초기화")}`}
            accessibilityState={{ disabled }}
            disabled={disabled}
            onPress={() =>
              step
                ? onShield(step)
                : void onAction({ action: "shield_reset", target })
            }
            style={{
              minHeight: 44,
              minWidth: 44,
              padding: 3,
              borderRadius: 8,
              borderWidth: 1,
              borderColor: "#8cd7f477",
              backgroundColor: "#122334e6",
              justifyContent: "center",
              opacity: disabled ? 0.4 : 1,
            }}
          >
            <Text
              adjustsFontSizeToFit
              numberOfLines={2}
              style={{
                color: "#c3edff",
                textAlign: "center",
                fontSize: 12,
                lineHeight: 15,
                fontWeight: "700",
              }}
            >
              {step ? t("보호막") + (step > 0 ? "+" : "−") : t("초기화")}
              {!!step && pending * step > 0
                ? `\n${pending > 0 ? "+" : "−"}${Math.abs(pending)}`
                : ""}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}
