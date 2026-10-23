import { PassivePanel } from "./passive-panel";
import { Image } from "react-native";
import React, { useEffect, useRef, useState } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";
import { calculatorArt } from "./calculator-art";
import { passiveImages } from "./calculator-passive-images";
import { passiveSymbols } from "./calculator-symbol-images";
import { passiveCleanImages } from "./calculator-clean-images";
const CleanPassives = React.createContext(false);
import { PassiveAura } from "./calculator-passive-effects";
import { passiveGet } from "./core";
import { useApp } from "./provider";
import {
  harmonyState,
  passiveActive,
  passiveArt,
  steppedCounter,
  taoInputLocked,
  visualAction,
  visualActive,
  visualDefinition,
  visualEnabled,
  visualLabel,
  visualValue,
  visualLayout,
  visualPresentation,
  visualTokenPositions,
  type VisualControl,
} from "./calculator-visual-model";
import type { Action, Player } from "./types";

type Props = {
  clean?: boolean;
  player: Player;
  target: "p1" | "p2";
  theme: string;
  accent: string;
  disabled: boolean;
  onAction: (a: Action) => Promise<void>;
  motionAllowed: () => boolean;
  ambientAllowed: boolean;
};
function SymbolArt({
  name,
  active = true,
}: {
  name: string;
  active?: boolean;
}) {
  const clean = React.useContext(CleanPassives);
  const source = clean
    ? passiveCleanImages[name]
    : passiveSymbols[name + (active ? "" : "-idle")];
  return source ? (
    <Image
      source={source}
      resizeMode="contain"
      style={{
        width: "100%",
        height: "100%",
        opacity: active ? 1 : clean ? 0.65 : 0.5,
      }}
      accessibilityElementsHidden
    />
  ) : null;
}
function Art({
  props,
  control,
  active,
}: {
  props: Props;
  control: VisualControl;
  active: boolean;
}) {
  const presentation = visualPresentation(props.theme, control.key);
  const progress = useRef(new Animated.Value(1)).current;
  const revision =
    control.type === "counter" && !control.max
      ? visualValue(props.player, control)
      : active;
  const previous = useRef(revision);
  useEffect(() => {
    if (previous.current === revision) return;
    previous.current = revision;
    progress.stopAnimation();
    if (!props.motionAllowed()) {
      progress.setValue(1);
      return;
    }
    progress.setValue(0);
    const animation = Animated.timing(progress, {
      toValue: 1,
      duration: 500,
      useNativeDriver: true,
      isInteraction: false,
    });
    animation.start();
    return () => animation.stop();
  }, [revision]);
  return (
    <Animated.View
      pointerEvents="none"
      style={{
        width: "100%",
        height: "100%",
        transform:
          props.theme === "keith"
            ? [
                { perspective: 400 },
                {
                  rotateY: progress.interpolate({
                    inputRange: [0, 1],
                    outputRange: ["-90deg", "0deg"],
                  }),
                },
              ]
            : [
                {
                  translateY: progress.interpolate({
                    inputRange: [0, 1],
                    outputRange: [
                      props.theme === "iomong"
                        ? -9
                        : props.theme === "delphy"
                          ? -5
                          : 0,
                      0,
                    ],
                  }),
                },
                {
                  scale: progress.interpolate({
                    inputRange: [0, 1],
                    outputRange: [0.93, 1],
                  }),
                },
              ],
      }}
    >
      {presentation.symbol ? (
        <SymbolArt name={presentation.symbol} active={active} />
      ) : (
        <Emblem theme={props.theme} active={active} />
      )}
    </Animated.View>
  );
}
function Aura({
  props,
  controlKey,
  active,
}: {
  props: Props;
  controlKey: string;
  active: boolean;
}) {
  const clean = React.useContext(CleanPassives);
  const p = visualPresentation(props.theme, controlKey);
  if (clean) return null;
  return p.effect ? (
    <PassiveAura
      active={active}
      allowed={props.ambientAllowed}
      kind={p.effect}
      color={p.color || props.accent}
    />
  ) : null;
}
function Flash({
  active,
  motionAllowed,
}: {
  active: boolean;
  motionAllowed: () => boolean;
}) {
  const value = useRef(new Animated.Value(0)).current;
  const before = useRef(active);
  useEffect(() => {
    const changed = before.current !== active;
    before.current = active;
    if (!changed) return;
    value.stopAnimation();
    if (!motionAllowed()) {
      value.setValue(0);
      return;
    }
    value.setValue(active ? 0.7 : 0.35);
    const animation = Animated.timing(value, {
      toValue: 0,
      duration: active ? 450 : 600,
      useNativeDriver: true,
    });
    animation.start();
    return () => animation.stop();
  }, [active]);
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        StyleSheet.absoluteFill,
        { backgroundColor: "#fff6d9", opacity: value, borderRadius: 10 },
      ]}
    />
  );
}
function Crop({ name, active }: { name: string; active: boolean }) {
  const clean = React.useContext(CleanPassives);
  const [box, setBox] = useState({ width: 64, height: 64 });
  if (clean) return <SymbolArt name={name} active={active} />;
  const info = passiveArt[name as keyof typeof passiveArt];
  if (!info) return <View style={s.crop} />;
  const [x = 0, y = 0, w = 1, h = 1] = info.crop;
  const scale = Math.max(box.width / w, box.height / h);
  return (
    <View
      pointerEvents="none"
      style={[s.crop, { opacity: active ? 1 : 0.5 }]}
      onLayout={(e) => {
        const { width, height } = e.nativeEvent.layout;
        if (width !== box.width || height !== box.height)
          setBox({ width, height });
      }}
    >
      <Image
        source={passiveImages[name]}
        resizeMode="stretch"
        style={{
          position: "absolute",
          width: info.width * scale,
          height: info.height * scale,
          left: (box.width - w * scale) / 2 - x * scale,
          top: (box.height - h * scale) / 2 - y * scale,
        }}
      />
    </View>
  );
}
function Emblem({ theme, active = true }: { theme: string; active?: boolean }) {
  const clean = React.useContext(CleanPassives);
  if (clean) return <SymbolArt name="seal" active={active} />;
  const art = calculatorArt[theme];
  return art ? (
    <Image
      key={"emblem-" + theme}
      source={art.emblem}
      resizeMode="contain"
      style={{ width: "100%", height: "100%", opacity: active ? 1 : 0.24 }}
      accessibilityElementsHidden
    />
  ) : null;
}
function TokenCounter({
  props,
  control,
  children,
}: {
  props: Props;
  control: VisualControl;
  children?: React.ReactNode;
}) {
  const { language } = useApp();
  const [width, setWidth] = useState(240);
  const value = Number(visualValue(props.player, control));
  const count = control.max || 0;
  const positions = visualTokenPositions(props.theme);
  const columns = count > 6 ? 5 : count === 6 ? 3 : count;
  const size = Math.max(
    44,
    Math.min(
      count >= 6 ? 44 : props.theme === "viola" ? 92 : 66,
      (width - 4 * (columns - 1)) / columns,
    ),
  );
  const label = visualLabel(control, language);
  return (
    <View
      style={
        positions
          ? [s.tokenStage, { width: props.theme === "wolf" ? 224 : 240 }]
          : s.tokens
      }
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
    >
      {Array.from({ length: count }, (_, i) => {
        const filled = i < value;
        return (
          <Pressable
            key={i}
            accessibilityRole="button"
            accessibilityLabel={
              label + " " + value + "/" + count + (filled ? " −1" : " +1")
            }
            accessibilityState={{ selected: filled, disabled: props.disabled }}
            disabled={props.disabled}
            onPress={() => {
              const a = visualAction(
                props.theme,
                props.player,
                props.target,
                control.key,
                steppedCounter(props.player, control, filled),
                language,
              );
              if (a) void props.onAction(a);
            }}
            style={[
              s.token,
              {
                width: positions ? 44 : size,
                height: positions ? 44 : size,
                borderColor: filled ? props.accent : "#aab9cc66",
                backgroundColor: filled ? props.accent + "22" : "#10192c55",
              },
              props.theme === "viola" && {
                borderRadius: size / 2,
                borderWidth: 1,
                backgroundColor: "#10172abf",
              },
              positions && {
                position: "absolute",
                left: positions[i]!.x * width - 22,
                top: positions[i]!.y * 176 - 22,
                overflow: "visible",
                borderWidth: 0,
              },
            ]}
          >
            {props.theme === "viola" ? (
              <Crop name="viola" active={filled} />
            ) : (
              <View
                style={{
                  flex: 1,
                  transform: [
                    { rotate: (positions?.[i]?.rotation || 0) + "deg" },
                  ],
                }}
              >
                <Art props={props} control={control} active={filled} />
              </View>
            )}
            <Aura props={props} controlKey={control.key} active={filled} />
            <Flash active={filled} motionAllowed={props.motionAllowed} />
          </Pressable>
        );
      })}
      {children}
    </View>
  );
}
function TaoSigil({
  props,
  active,
  locked,
}: {
  props: Props;
  active: boolean;
  locked: boolean;
}) {
  const { language } = useApp();
  const [width, setWidth] = useState(120),
    [shown, setShown] = useState(active);
  const progress = useRef(new Animated.Value(active ? 1 : 0)).current;
  const previous = useRef(active);
  useEffect(() => {
    if (previous.current === active) return;
    previous.current = active;
    if (!props.motionAllowed()) {
      progress.setValue(active ? 1 : 0);
      setShown(active);
      return;
    }
    setShown(true);
    const animation = Animated.timing(progress, {
      toValue: active ? 1 : 0,
      duration: active ? 500 : 450,
      useNativeDriver: true,
    });
    animation.start(({ finished }) => {
      if (finished && !active) setShown(false);
    });
    return () => animation.stop();
  }, [active]);
  const size = Math.max(88, Math.min(132, width));
  const effect = String(passiveGet(props.player, "harmony_effect", ""));
  return (
    <View
      style={s.taoCenter}
      onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
    >
      <Text style={s.effect} accessibilityLiveRegion="polite">
        {active && effect ? (effect === "fp_1" ? "+1FP" : "+100DMG") : ""}
      </Text>
      {shown ? (
        <Animated.View
          style={{
            width: size,
            height: size,
            borderRadius: size / 2,
            overflow: "hidden",
            backgroundColor: "#f7f5ed",
            opacity: progress,
            transform: [
              {
                rotate: progress.interpolate({
                  inputRange: [0, 1],
                  outputRange: ["-180deg", "0deg"],
                }),
              },
              {
                scale: progress.interpolate({
                  inputRange: [0, 1],
                  outputRange: [0.25, 1],
                }),
              },
            ],
          }}
        >
          <View
            pointerEvents="none"
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              bottom: 0,
              width: "50%",
              backgroundColor: "#090c17",
            }}
          />
          <View
            pointerEvents="none"
            style={{
              position: "absolute",
              left: size / 4,
              top: 0,
              width: size / 2,
              height: size / 2,
              borderRadius: size / 4,
              backgroundColor: "#090c17",
            }}
          />
          <View
            pointerEvents="none"
            style={{
              position: "absolute",
              left: size / 4,
              bottom: 0,
              width: size / 2,
              height: size / 2,
              borderRadius: size / 4,
              backgroundColor: "#f7f5ed",
            }}
          />
          <View
            pointerEvents="none"
            style={{
              position: "absolute",
              left: size * 0.44,
              top: size * 0.19,
              width: size * 0.12,
              height: size * 0.12,
              borderRadius: size * 0.06,
              backgroundColor: "#f7f5ed",
            }}
          />
          <View
            pointerEvents="none"
            style={{
              position: "absolute",
              left: size * 0.44,
              bottom: size * 0.19,
              width: size * 0.12,
              height: size * 0.12,
              borderRadius: size * 0.06,
              backgroundColor: "#090c17",
            }}
          />
          <Aura props={props} controlKey="harmony" active={active} />
          {["fp_1", "damage_100"].map((choice, i) => (
            <Pressable
              key={choice}
              accessibilityRole="button"
              accessibilityLabel={choice === "fp_1" ? "+1FP" : "+100DMG"}
              accessibilityState={{
                selected: effect === choice,
                disabled: props.disabled || !active,
              }}
              disabled={props.disabled || !active}
              onPress={() => {
                const a = visualAction(
                  "tao",
                  props.player,
                  props.target,
                  "harmony_effect",
                  choice,
                  language,
                );
                if (a) void props.onAction(a);
              }}
              style={{
                position: "absolute",
                top: 0,
                bottom: 0,
                left: i === 0 ? 0 : undefined,
                right: i === 1 ? 0 : undefined,
                width: "50%",
                justifyContent: "center",
                alignItems: "center",
                backgroundColor:
                  effect === choice ? "#ffd47d44" : "transparent",
                borderColor: "#ffe4a2",
                borderWidth: effect === choice ? 1 : 0,
              }}
            >
              {locked && (
                <Text
                  adjustsFontSizeToFit
                  numberOfLines={1}
                  style={s.choiceHint}
                >
                  {choice === "fp_1" ? "+1FP" : "+100DMG"}
                </Text>
              )}
            </Pressable>
          ))}
        </Animated.View>
      ) : (
        <View
          style={{
            width: size,
            height: size,
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <View style={[s.idleOrb, { backgroundColor: "#f7f5ed" }]} />
          <View
            style={[
              s.idleOrb,
              {
                backgroundColor: "#090c17",
                borderColor: "#a6b5d0",
                borderWidth: 1,
              },
            ]}
          />
        </View>
      )}
    </View>
  );
}
function Tao(props: Props) {
  const { language } = useApp();
  const active = harmonyState(props.player),
    locked = taoInputLocked(props.player);
  const controls = visualDefinition("tao").controls;
  function bar(key: string, white: boolean) {
    const control = controls.find((c) => c.key === key)!;
    const value = Number(visualValue(props.player, control));
    return (
      <View style={s.bar}>
        {Array.from({ length: 4 }, (_, i) => {
          const filled = i < value;
          return (
            <Pressable
              key={i}
              accessibilityRole="button"
              accessibilityLabel={
                visualLabel(control, language) +
                " " +
                value +
                "/4" +
                (filled ? " −1" : " +1")
              }
              accessibilityState={{
                selected: filled,
                disabled: props.disabled || locked,
              }}
              disabled={props.disabled || locked}
              onPress={() => {
                const a = visualAction(
                  "tao",
                  props.player,
                  props.target,
                  key,
                  steppedCounter(props.player, control, filled),
                  language,
                );
                if (a) void props.onAction(a);
              }}
              style={[
                s.barCell,
                {
                  borderStyle: "solid",
                  borderColor: filled
                    ? white
                      ? "#fff4da"
                      : "#c2c9df"
                    : "#91a3be99",
                  backgroundColor: filled
                    ? white
                      ? "#faf9f0"
                      : "#080b15"
                    : "#10192cd9",
                },
              ]}
            >
              <View
                pointerEvents="none"
                style={{
                  flex: 1,
                  borderWidth: filled ? 1 : 0,
                  borderColor: white ? "#fff" : "#5c627b",
                  backgroundColor: filled
                    ? white
                      ? "#f7f5ed"
                      : "#080b15"
                    : "#a8b4c8",
                  borderRadius: 3,
                  opacity: filled ? 1 : 0.2,
                }}
              />
              <Aura props={props} controlKey={key} active={filled} />
            </Pressable>
          );
        })}
      </View>
    );
  }
  return (
    <View style={s.tao}>
      {bar("yang_counter", true)}
      <TaoSigil props={props} active={active} locked={locked} />
      {bar("yin_counter", false)}
    </View>
  );
}
function Rita(props: Props) {
  const { language } = useApp();
  const controls = visualDefinition("rita").controls;
  const light = passiveActive(passiveGet(props.player, "light_lumen", false));
  const role = String(passiveGet(props.player, "rita_role", ""));
  const lumen = controls.find((c) => c.key === "light_lumen")!;
  const roles = controls.find((c) => c.key === "rita_role")!;
  function set(key: string, value: unknown) {
    const a = visualAction(
      "rita",
      props.player,
      props.target,
      key,
      value,
      language,
    );
    if (a) void props.onAction(a);
  }
  return (
    <View style={s.rita}>
      <Pressable
        accessibilityRole="switch"
        accessibilityLabel={visualLabel(lumen, language)}
        accessibilityState={{ checked: light, disabled: props.disabled }}
        disabled={props.disabled}
        onPress={() => set("light_lumen", !light)}
        style={[
          s.lumen,
          {
            borderColor: light ? props.accent : "#6a778d44",
            backgroundColor: light ? props.accent + "22" : "transparent",
            transform: [{ rotate: props.clean ? "0deg" : "45deg" }],
          },
        ]}
      >
        <View
          style={{
            width: props.clean ? "100%" : 57,
            height: props.clean ? "100%" : 76,
            transform: [{ rotate: props.clean ? "0deg" : "-45deg" }],
          }}
        >
          <Crop name="condenser" active={light} />
        </View>
        <Flash active={light} motionAllowed={props.motionAllowed} />
        <Aura props={props} controlKey="light_lumen" active={light} />
      </Pressable>
      <View style={s.legionRow}>
        {(roles.choices || []).map((item) => {
          const value = String(item.value ?? item.key);
          const on = role === value;
          const label = (item as any).labels?.[language] || item.label;
          return (
            <Pressable
              key={value}
              accessibilityRole="button"
              accessibilityLabel={label}
              accessibilityState={{ selected: on, disabled: props.disabled }}
              disabled={props.disabled}
              onPress={() => set("rita_role", on ? "" : value)}
              style={[
                s.diamond,
                {
                  borderColor: on ? props.accent : "#a2adc166",
                  backgroundColor: on
                    ? props.clean
                      ? props.accent + "22"
                      : props.accent
                    : "#17243b66",
                  ...(props.clean && {
                    transform: [{ rotate: "0deg" }],
                    borderRadius: 8,
                  }),
                },
              ]}
            >
              <View
                style={{
                  width: props.clean ? "100%" : "142%",
                  height: props.clean ? "100%" : "142%",
                  transform: [{ rotate: props.clean ? "0deg" : "-45deg" }],
                }}
              >
                <Crop name={value} active={on} />
              </View>
              <Flash active={on} motionAllowed={props.motionAllowed} />
              <Aura props={props} controlKey="rita_role" active={on} />
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
function ThemedSwitch({
  props,
  control,
  stage = false,
}: {
  props: Props;
  control: VisualControl;
  stage?: boolean;
}) {
  const { language } = useApp();
  const active = visualActive(props.player, control),
    enabled = visualEnabled(props.player, control);
  const layout = visualLayout(props.theme);
  const sizes: Record<string, { width: number; height: number }> = {
    focus: { width: 146, height: 132 },
    core: { width: 136, height: 136 },
    workshop: { width: 96, height: 78 },
    "calling-card": { width: 102, height: 138 },
    cockpit: { width: 154, height: 132 },
    "blue-flame": { width: 142, height: 150 },
  };
  const size = stage
    ? {
        width: props.theme === "yohan" ? 76 : 60,
        height: props.theme === "yohan" ? 76 : 60,
      }
    : sizes[layout] || { width: 100, height: 64 };
  return (
    <Pressable
      accessibilityRole={control.type === "status" ? "text" : "switch"}
      accessibilityLabel={visualLabel(control, language)}
      accessibilityState={{
        checked: active,
        disabled: props.disabled || !enabled,
      }}
      disabled={props.disabled || !enabled || control.type === "status"}
      onPress={() => {
        const a = visualAction(
          props.theme,
          props.player,
          props.target,
          control.key,
          !active,
          language,
        );
        if (a) void props.onAction(a);
      }}
      style={[
        s.switch,
        {
          ...size,
          minHeight: size.height,
          maxHeight: size.height,
          flex: 0,
          borderWidth: props.clean ? 1 : 0,
          borderRadius: layout === "core" ? 70 : 12,
          backgroundColor: props.clean
            ? "#172234"
            : control.type === "status"
              ? "transparent"
              : "#10192c55",
          borderColor: active ? props.accent : "#66778d66",
          opacity: !enabled && !active ? 0.55 : 1,
        },
        stage && {
          position: "absolute",
          left: "50%",
          top: props.theme === "rev" ? "67%" : "50%",
          transform: [
            { translateX: -size.width / 2 },
            { translateY: -size.height / 2 },
          ],
          overflow: "visible",
        },
      ]}
    >
      <View style={{ width: "100%", height: "100%" }}>
        <Art props={props} control={control} active={active} />
      </View>
      <Flash active={active} motionAllowed={props.motionAllowed} />
      <Aura props={props} controlKey={control.key} active={active} />
    </Pressable>
  );
}
function FreeCounter({
  props,
  control,
}: {
  props: Props;
  control: VisualControl;
}) {
  const { language } = useApp();
  const raw = Number(visualValue(props.player, control)),
    label = visualLabel(control, language);
  function set(value: number) {
    const a = visualAction(
      props.theme,
      props.player,
      props.target,
      control.key,
      value,
      language,
    );
    if (a) void props.onAction(a);
  }
  return (
    <View style={s.freeCounter}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label + " −1"}
        accessibilityState={{ disabled: props.disabled || raw <= 0 }}
        disabled={props.disabled || raw <= 0}
        onPress={() => set(raw - 1)}
        style={[s.step, { opacity: props.disabled || raw <= 0 ? 0.4 : 1 }]}
      >
        <Text style={s.stepText}>−</Text>
      </Pressable>
      <View accessibilityLabel={label + " " + raw} style={s.freeImage}>
        <View style={{ position: "absolute", top: 0, width: 112, height: 100 }}>
          <Art props={props} control={control} active={raw > 0} />
        </View>
        <Aura props={props} controlKey={control.key} active={raw > 0} />
        <Text style={s.number}>{raw}</Text>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label + " +1"}
        accessibilityState={{ disabled: props.disabled }}
        disabled={props.disabled}
        onPress={() => set(raw + 1)}
        style={[s.step, { opacity: props.disabled ? 0.4 : 1 }]}
      >
        <Text style={s.stepText}>+</Text>
      </Pressable>
    </View>
  );
}
export function VisualPassives(props: Props) {
  return (
    <CleanPassives.Provider value={!!props.clean}>
      <VisualPassivesContent {...props} />
    </CleanPassives.Provider>
  );
}
function VisualPassivesContent(props: Props) {
  if (
    props.player.character?.trait_card_id &&
    !props.player.character.trait_config?.legacy_character_actions
  )
    return (
      <PassivePanel
        player={props.player}
        target={props.target}
        definition={props.player.character.passive || { controls: [] }}
        disabled={props.disabled}
        onAction={props.onAction}
      />
    );
  if (props.theme === "tao") return <Tao {...props} />;
  if (props.theme === "rita") return <Rita {...props} />;
  const controls = visualDefinition(props.theme).controls;
  if (visualLayout(props.theme) === "empty") return <View style={s.empty} />;
  if (!controls.length)
    return (
      <View style={s.empty}>
        <View style={{ width: 80, height: 80, opacity: 0.35 }}>
          <SymbolArt name="seal" />
        </View>
      </View>
    );
  if (visualTokenPositions(props.theme)) {
    const counter = controls.find((c) => c.type === "counter")!;
    const toggle = controls.find((c) => c.type !== "counter")!;
    return (
      <View style={s.generic}>
        <TokenCounter props={props} control={counter}>
          <ThemedSwitch props={props} control={toggle} stage />
        </TokenCounter>
      </View>
    );
  }
  return (
    <View style={[s.generic, props.theme === "delphy" && { gap: 4 }]}>
      {controls.map((control) =>
        control.type === "counter" ? (
          control.max ? (
            <TokenCounter key={control.key} props={props} control={control} />
          ) : (
            <FreeCounter key={control.key} props={props} control={control} />
          )
        ) : (
          <ThemedSwitch key={control.key} props={props} control={control} />
        ),
      )}
    </View>
  );
}
const s = StyleSheet.create({
  crop: { position: "absolute", inset: 0, overflow: "hidden" },
  tokenStage: { height: 176, maxWidth: "100%", position: "relative" },
  tokens: {
    width: "100%",
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    alignItems: "center",
    gap: 4,
  },
  token: {
    minWidth: 44,
    minHeight: 44,
    borderWidth: 1,
    borderRadius: 10,
    padding: 3,
    overflow: "hidden",
  },
  generic: {
    flex: 1,
    minHeight: 0,
    justifyContent: "center",
    alignItems: "center",
    gap: 6,
  },
  empty: { flex: 1, alignItems: "center", justifyContent: "center" },
  switch: {
    width: 100,
    minHeight: 54,
    maxHeight: 64,
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderRadius: 12,
    overflow: "hidden",
  },
  indicator: { position: "absolute", right: 4, bottom: 2, fontSize: 11 },
  freeCounter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  step: {
    width: 44,
    height: 44,
    borderWidth: 1,
    borderColor: "#9baec566",
    borderRadius: 8,
    backgroundColor: "#10192c99",
    alignItems: "center",
    justifyContent: "center",
  },
  stepText: { fontSize: 23, color: "#f6efd9", fontWeight: "800" },
  freeImage: {
    width: 112,
    height: 128,
    justifyContent: "center",
    alignItems: "center",
  },
  number: {
    position: "absolute",
    bottom: 0,
    width: "100%",
    height: 32,
    lineHeight: 32,
    textAlign: "center",
    borderRadius: 20,
    backgroundColor: "#0a1424bb",
    color: "#fff",
    fontSize: 27,
    fontWeight: "900",
    textShadowColor: "#000",
    textShadowRadius: 6,
  },
  tao: { flex: 1, flexDirection: "row", alignItems: "center", gap: 6 },
  bar: { width: 44, flexDirection: "column-reverse", gap: 1 },
  barCell: {
    width: 44,
    height: 44,
    minHeight: 44,
    padding: 3,
    borderWidth: 1,
    borderRadius: 6,
  },
  taoCenter: {
    flex: 1,
    minWidth: 0,
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  effect: {
    height: 22,
    lineHeight: 22,
    fontSize: 15,
    color: "#fff5d5",
    fontWeight: "900",
  },
  choiceHint: {
    fontSize: 10,
    fontWeight: "900",
    color: "#fff",
    backgroundColor: "#0a1224b8",
    paddingVertical: 4,
    paddingHorizontal: 1,
    borderRadius: 4,
  },
  idleOrb: { width: 24, height: 24, borderRadius: 12 },
  rita: {
    flex: 1,
    minHeight: 0,
    justifyContent: "center",
    alignItems: "center",
    gap: 26,
    paddingVertical: 9,
  },
  lumen: {
    width: 48,
    height: 48,
    borderWidth: 1,
    borderRadius: 6,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
  legionRow: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    gap: 25,
    width: "100%",
    paddingHorizontal: 15,
  },
  diamond: {
    width: 51,
    height: 51,
    minWidth: 44,
    minHeight: 44,
    transform: [{ rotate: "45deg" }],
    borderWidth: 2,
    overflow: "hidden",
    alignItems: "center",
    justifyContent: "center",
  },
});
