import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type {
  Player,
  Action,
  PassiveDefinition,
  PassiveControl,
} from "./types";
import { conditionMet, passiveActions, passiveGet } from "./core";
import { passiveActive, nextTaoEffect } from "./calculator-display";
import { useApp } from "./provider";
import { styles, Button, Input, colors } from "./ui";

type Props = {
  player: Player;
  target: "p1" | "p2";
  definition: PassiveDefinition;
  disabled: boolean;
  onAction: (a: Action) => void;
};
export function PassivePanel(props: Props) {
  const { player, target, definition, disabled, onAction } = props;
  const { t } = useApp();
  const controls = [
    ...(definition.controls || []),
    ...(definition.badges || []).map((b) => ({
      ...b,
      type: b.type || "status",
    })),
  ];
  function set(c: PassiveControl, value: unknown) {
    onAction(passiveActions(player, definition, target, c.key, value, c.label));
  }
  if (definition.adapter === "tao") return <TaoPanel {...props} />;
  const repeatedTitle =
    controls.length === 1 && controls[0]?.label === definition.title;
  return (
    <View>
      {!!definition.title && !repeatedTitle && (
        <Text style={styles.text}>{definition.title}</Text>
      )}
      {!!definition.description && (
        <Text style={styles.muted}>{definition.description}</Text>
      )}
      {controls
        .filter((c) => !c.visibleWhen || conditionMet(c.visibleWhen, player))
        .map((c) => {
          const value = passiveGet(player, c.key, c.default ?? c.initial ?? 0);
          const blocked =
            disabled || (!!c.enableWhen && !conditionMet(c.enableWhen, player));
          const active =
            c.type === "status"
              ? conditionMet(c.condition, player)
              : c.type === "latchedStatus"
                ? (!!c.activateWhen && conditionMet(c.activateWhen, player)) ||
                  (passiveActive(value) &&
                    (!c.keepWhile || conditionMet(c.keepWhile, player)))
                : passiveActive(value);
          return (
            <View key={c.key} style={passives.control}>
              {c.type === "counter" ? (
                <Counter
                  control={c}
                  value={Number(value)}
                  disabled={blocked}
                  onSet={(v) => set(c, v)}
                />
              ) : c.type === "toggle" ? (
                <Toggle
                  label={c.label}
                  active={active}
                  disabled={blocked}
                  onPress={() => set(c, !active)}
                />
              ) : c.type === "thresholdAction" ? (
                <Toggle
                  label={c.label}
                  active={active}
                  disabled={
                    blocked ||
                    (!active &&
                      !conditionMet(
                        c.requires || c.activateWhen || c.condition,
                        player,
                      ))
                  }
                  onPress={() => {
                    const actions: Action[] = [
                      {
                        action: "passive",
                        target,
                        key: c.key,
                        value: !active,
                        label: c.label,
                      },
                    ];
                    if (!active)
                      for (const key of c.resetKeys || [])
                        actions.push({
                          action: "passive",
                          target,
                          key,
                          value: 0,
                          label: key,
                        });
                    onAction({ action: "batch", actions });
                  }}
                />
              ) : c.type === "status" || c.type === "latchedStatus" ? (
                <View
                  accessibilityRole="text"
                  accessibilityLabel={`${c.label}: ${t(active ? "활성" : "비활성")}`}
                  style={[passives.toggle, active && passives.active]}
                >
                  <Text
                    style={[passives.toggleText, active && passives.activeText]}
                  >
                    {c.label}
                  </Text>
                </View>
              ) : c.type === "choice" ? (
                <>
                  <Text style={[styles.muted, passives.label]}>{c.label}</Text>
                  <View style={passives.choices}>
                    {(c.choices || []).map((choice, i) => (
                      <Toggle
                        key={i}
                        label={choice.label}
                        active={value === (choice.value ?? choice.key)}
                        disabled={blocked}
                        onPress={() => set(c, choice.value ?? choice.key)}
                      />
                    ))}
                  </View>
                </>
              ) : (
                <>
                  <Text style={styles.muted}>{c.label}</Text>
                  <Input
                    editable={!blocked}
                    onEndEditing={(e) => set(c, e.nativeEvent.text)}
                    defaultValue={String(value ?? "")}
                  />
                </>
              )}
            </View>
          );
        })}
    </View>
  );
}
function Counter({
  control,
  value,
  disabled,
  onSet,
  compact = false,
}: {
  control: PassiveControl;
  value: number;
  disabled: boolean;
  onSet: (value: number) => void;
  compact?: boolean;
}) {
  const { t } = useApp();
  return (
    <View style={{ alignItems: "center", minWidth: 0 }}>
      <Text
        numberOfLines={1}
        maxFontSizeMultiplier={1.3}
        style={[styles.muted, passives.label]}
      >
        {control.label}
      </Text>
      <View style={passives.counter}>
        <Step
          label={`${control.label} -1`}
          text="−"
          compact={compact}
          disabled={disabled || value <= 0}
          onPress={() => onSet(Math.max(0, value - 1))}
        />
        <Step
          label={`${control.label} ${value}, ${t("초기화")}`}
          text={
            String(value) + (control.max !== undefined ? "/" + control.max : "")
          }
          compact={compact}
          disabled={disabled || value <= 0}
          onPress={() => onSet(0)}
          value
        />
        <Step
          label={`${control.label} +1`}
          text="+"
          compact={compact}
          disabled={
            disabled || (control.max !== undefined && value >= control.max)
          }
          onPress={() => onSet(Math.min(control.max ?? 32767, value + 1))}
        />
      </View>
    </View>
  );
}
function Step({
  label,
  text,
  onPress,
  disabled,
  compact,
  value,
}: {
  label: string;
  text: string;
  onPress: () => void;
  disabled: boolean;
  compact: boolean;
  value?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
      disabled={disabled}
      hitSlop={4}
      onPress={onPress}
      style={[
        passives.step,
        {
          width: value ? (compact ? 37 : 48) : compact ? 28 : 38,
          height: compact ? 32 : 38,
        },
        disabled && { opacity: 0.4 },
      ]}
    >
      <Text
        adjustsFontSizeToFit
        numberOfLines={1}
        maxFontSizeMultiplier={1.3}
        style={passives.stepText}
      >
        {text}
      </Text>
    </Pressable>
  );
}
function Toggle({
  label,
  active,
  disabled,
  onPress,
}: {
  label: string;
  active: boolean;
  disabled: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={label}
      accessibilityState={{ checked: active, disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[
        passives.toggle,
        active && passives.active,
        disabled && { opacity: 0.4 },
      ]}
    >
      <Text
        numberOfLines={2}
        adjustsFontSizeToFit
        maxFontSizeMultiplier={1.3}
        style={[passives.toggleText, active && passives.activeText]}
      >
        {label}
      </Text>
    </Pressable>
  );
}
function TaoPanel({ player, target, definition, disabled, onAction }: Props) {
  const { t } = useApp();
  const controls = definition.controls || [];
  const counters = controls.filter((c) =>
    ["yang_counter", "yin_counter"].includes(c.key),
  );
  const yang = Number(passiveGet(player, "yang_counter"));
  const yin = Number(passiveGet(player, "yin_counter"));
  const harmony =
    (yang === 4 && yin === 4) ||
    (passiveActive(passiveGet(player, "harmony", false)) &&
      yang >= 3 &&
      yin >= 3);
  const effects = controls.find((c) => c.key === "harmony_effect");
  const current = passiveGet(player, "harmony_effect", "");
  return (
    <View style={passives.tao}>
      <View style={passives.taoCounters}>
        {counters.map((c) => (
          <View key={c.key} style={{ flex: 1, minWidth: 0 }}>
            <Counter
              compact
              control={c}
              value={Number(passiveGet(player, c.key))}
              disabled={disabled}
              onSet={(v) =>
                onAction(
                  passiveActions(player, definition, target, c.key, v, c.label),
                )
              }
            />
          </View>
        ))}
      </View>
      {harmony && effects && (
        <View style={{ marginTop: 4 }}>
          <Text style={[styles.muted, passives.label, { marginBottom: 3 }]}>
            {controls.find((c) => c.key === "harmony")?.label || t("조화")}
          </Text>
          <View style={passives.taoEffects}>
            {(effects.choices || [])
              .filter((choice) => choice.value || choice.key)
              .map((choice, i) => {
                const selected = String(choice.value ?? choice.key);
                return (
                  <View key={i} style={{ flex: 1 }}>
                    <Toggle
                      label={choice.label}
                      active={current === selected}
                      disabled={disabled}
                      onPress={() => {
                        const effect = passiveActions(
                          player,
                          definition,
                          target,
                          effects.key,
                          nextTaoEffect(current, selected),
                          effects.label,
                        );
                        if (
                          !passiveActive(passiveGet(player, "harmony", false))
                        )
                          onAction({
                            action: "batch",
                            actions: [
                              {
                                action: "passive",
                                target,
                                key: "harmony",
                                value: true,
                                label: t("조화"),
                              },
                              effect,
                            ],
                          });
                        else onAction(effect);
                      }}
                    />
                  </View>
                );
              })}
          </View>
        </View>
      )}
    </View>
  );
}
const passives = StyleSheet.create({
  control: { marginVertical: 5 },
  label: { textAlign: "center", marginBottom: 4 },
  counter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
  },
  choices: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 6,
  },
  step: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.line,
    borderRadius: 7,
  },
  stepText: { color: colors.accent, fontSize: 16, fontWeight: "700" },
  toggle: {
    minHeight: 34,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: "#242424",
    justifyContent: "center",
    alignItems: "center",
  },
  toggleText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: "700",
    textAlign: "center",
  },
  active: { backgroundColor: colors.accent, borderColor: colors.accent },
  activeText: { color: colors.bg },
  tao: { paddingTop: 1 },
  taoCounters: { flexDirection: "row", gap: 6 },
  taoEffects: { flexDirection: "row", gap: 6 },
});
