import React from "react";
import { View, Text } from "react-native";
import type { Player, Action, PassiveDefinition } from "./types";
import { conditionMet, passiveActions, passiveGet } from "./core";
import { styles, Button, Input } from "./ui";
export function PassivePanel({
  player,
  target,
  definition,
  disabled,
  onAction,
}: {
  player: Player;
  target: "p1" | "p2";
  definition: PassiveDefinition;
  disabled: boolean;
  onAction: (a: Action) => void;
}) {
  function set(key: string, value: any, label: string) {
    onAction(passiveActions(player, definition, target, key, value, label));
  }
  return (
    <View>
      <Text style={styles.text}>{definition.title}</Text>
      {definition.description && (
        <Text style={styles.muted}>{definition.description}</Text>
      )}
      {[
        ...(definition.controls || []),
        ...(definition.badges || []).map((b) => ({
          ...b,
          type: b.type || "status",
        })),
      ]
        .filter((c) => !c.visibleWhen || conditionMet(c.visibleWhen, player))
        .map((c) => {
          const value = passiveGet(player, c.key, c.default ?? c.initial ?? 0),
            blocked =
              disabled ||
              (!!c.enableWhen && !conditionMet(c.enableWhen, player));
          const active =
            c.type === "status"
              ? conditionMet(c.condition, player)
              : c.type === "latchedStatus"
                ? (!!c.activateWhen && conditionMet(c.activateWhen, player)) ||
                  (!!value &&
                    (!c.keepWhile || conditionMet(c.keepWhile, player)))
                : !!value;
          return (
            <View key={c.key} style={{ marginVertical: 6 }}>
              <Text style={styles.muted}>{c.label}</Text>
              {c.type === "counter" ? (
                <View style={styles.row}>
                  <Button
                    label="−"
                    disabled={blocked || Number(value) <= 0}
                    onPress={() =>
                      set(c.key, Math.max(0, Number(value) - 1), c.label)
                    }
                  />
                  <Button
                    label={
                      String(value) + (c.max !== undefined ? "/" + c.max : "")
                    }
                    disabled={blocked || !Number(value)}
                    onPress={() => set(c.key, 0, c.label)}
                  />
                  <Button
                    label="+"
                    disabled={
                      blocked || (c.max !== undefined && Number(value) >= c.max)
                    }
                    onPress={() =>
                      set(
                        c.key,
                        Math.min(c.max ?? 32767, Number(value) + 1),
                        c.label,
                      )
                    }
                  />
                </View>
              ) : c.type === "toggle" ? (
                <Button
                  label={active ? "ON" : "OFF"}
                  disabled={blocked}
                  onPress={() => set(c.key, !active, c.label)}
                />
              ) : c.type === "choice" ? (
                <View style={styles.row}>
                  {(c.choices || []).map((choice, i) => (
                    <Button
                      key={i}
                      label={
                        choice.label +
                        (value === (choice.value ?? choice.key) ? " ✓" : "")
                      }
                      disabled={blocked}
                      onPress={() =>
                        set(c.key, choice.value ?? choice.key, c.label)
                      }
                    />
                  ))}
                </View>
              ) : c.type === "thresholdAction" ? (
                <Button
                  label={active ? "ON" : "OFF"}
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
                <Text style={styles.text}>
                  {active ? c.activeText || "ON" : c.inactiveText || "OFF"}
                </Text>
              ) : (
                <Input
                  editable={!blocked}
                  onEndEditing={(event) =>
                    set(c.key, event.nativeEvent.text, c.label)
                  }
                  defaultValue={String(value ?? "")}
                />
              )}
            </View>
          );
        })}
    </View>
  );
}
