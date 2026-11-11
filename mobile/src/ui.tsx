import React, { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  View,
  Text,
  Pressable,
  TextInput,
  StyleSheet,
  type StyleProp,
  type ViewStyle,
} from "react-native";
import { Image } from "expo-image";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";
import Markdown from "react-native-markdown-display";
import { useApp } from "./provider";
import { cachedImage } from "./catalog";
import { absoluteUrl } from "./api";

// ── 디자인 토큰 ────────────────────────────────────────────────
// 기존 키(bg, panel, line, text, muted, accent, danger)는 계산기·파티 화면도 쓰므로 값을 유지한다.
export const colors = {
  bg: "#111111",
  panel: "#1b1b1b",
  surface2: "#252525",
  line: "#303030",
  text: "#f4f1ea",
  muted: "#b8b0a4",
  subtle: "#8a847b",
  accent: "#e0b45b",
  accentSoft: "rgba(224, 180, 91, 0.16)",
  onAccent: "#1c1608",
  danger: "#ff8d9b",
  dangerSoft: "rgba(255, 141, 155, 0.14)",
  success: "#7fd1a6",
};
export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 };
/** 최소 터치 영역(px). 버튼·행·아이콘 버튼 모두 이 높이 이상을 유지한다. */
export const touch = 44;

export const type = StyleSheet.create({
  display: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "800",
    letterSpacing: -0.4,
  },
  title: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.2,
  },
  heading: { color: colors.text, fontSize: 17, fontWeight: "600" },
  body: { color: colors.text, fontSize: 15, lineHeight: 21 },
  label: { color: colors.muted, fontSize: 13, fontWeight: "600" },
  caption: { color: colors.muted, fontSize: 12, lineHeight: 16 },
  number: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "700",
    fontVariant: ["tabular-nums"],
  },
});

export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, padding: space.lg },
  panel: {
    backgroundColor: colors.panel,
    borderRadius: radius.lg,
    padding: 14,
    marginBottom: space.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    flexWrap: "wrap",
  },
  title: {
    color: colors.text,
    fontSize: 20,
    fontWeight: "700",
    letterSpacing: -0.2,
    marginBottom: space.md,
  },
  text: { color: colors.text, fontSize: 15 },
  muted: { color: colors.muted, fontSize: 12 },
  // 예전 화면(계산기 등)이 직접 쓰는 버튼 스타일. 새 코드는 <Button>을 쓴다.
  button: {
    backgroundColor: colors.surface2,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  buttonText: { color: colors.accent, fontWeight: "600" },
  input: {
    color: colors.text,
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    minHeight: 48,
    fontSize: 15,
    marginBottom: 10,
  },
});

// ── 아이콘·햅틱 ───────────────────────────────────────────────
export type IconName = keyof typeof Ionicons.glyphMap;
export function Icon({
  name,
  size = 20,
  color = colors.text,
}: {
  name: IconName;
  size?: number;
  color?: string;
}) {
  return <Ionicons name={name} size={size} color={color} />;
}
/** 가벼운 촉각 피드백. 지원하지 않는 기기에서는 조용히 무시한다. */
export function tapFeedback(kind: "light" | "selection" | "warning" = "light") {
  const run =
    kind === "selection"
      ? Haptics.selectionAsync()
      : kind === "warning"
        ? Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning)
        : Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
  run.catch(() => undefined);
}
const pressedStyle: ViewStyle = { opacity: 0.85, transform: [{ scale: 0.97 }] };

// ── 버튼 ─────────────────────────────────────────────────────
export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
const buttonTheme: Record<
  ButtonVariant,
  { bg: string; fg: string; border: string }
> = {
  primary: { bg: colors.accent, fg: colors.onAccent, border: colors.accent },
  secondary: { bg: colors.surface2, fg: colors.accent, border: colors.line },
  ghost: { bg: "transparent", fg: colors.accent, border: "transparent" },
  danger: { bg: colors.dangerSoft, fg: colors.danger, border: "transparent" },
};
export function Button({
  label,
  onPress,
  disabled = false,
  danger = false,
  variant,
  icon,
  size = "md",
  block = false,
  loading = false,
  style,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  /** 예전 API. variant="danger"와 같다. */
  danger?: boolean;
  variant?: ButtonVariant;
  icon?: IconName;
  size?: "sm" | "md";
  /** 가로를 꽉 채운다. */
  block?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { t } = useApp();
  const kind: ButtonVariant = variant ?? (danger ? "danger" : "secondary");
  const theme = buttonTheme[kind];
  const small = size === "sm";
  const inactive = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t(label)}
      accessibilityState={{ disabled: inactive, busy: loading }}
      disabled={inactive}
      onPress={() => {
        if (kind === "primary") tapFeedback();
        else if (kind === "danger") tapFeedback("warning");
        onPress();
      }}
      hitSlop={small ? 6 : 0}
      style={({ pressed }) => [
        buttonStyles.base,
        small && buttonStyles.small,
        block && buttonStyles.block,
        { backgroundColor: theme.bg, borderColor: theme.border },
        inactive && { opacity: 0.4 },
        pressed && pressedStyle,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={theme.fg} />
      ) : (
        icon && <Ionicons name={icon} size={small ? 16 : 18} color={theme.fg} />
      )}
      <Text
        numberOfLines={1}
        style={[
          buttonStyles.label,
          small && buttonStyles.smallLabel,
          { color: theme.fg },
        ]}
      >
        {t(label)}
      </Text>
    </Pressable>
  );
}
export function IconButton({
  icon,
  label,
  onPress,
  disabled = false,
  filled = false,
  color,
  size = 22,
}: {
  icon: IconName;
  /** 화면 낭독기용 이름. 번역 키를 넣는다. */
  label: string;
  onPress: () => void;
  disabled?: boolean;
  filled?: boolean;
  color?: string;
  size?: number;
}) {
  const { t } = useApp();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t(label)}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      hitSlop={4}
      style={({ pressed }) => [
        buttonStyles.icon,
        filled && { backgroundColor: colors.surface2 },
        disabled && { opacity: 0.4 },
        pressed && { backgroundColor: colors.surface2, opacity: 0.85 },
      ]}
    >
      <Ionicons
        name={icon}
        size={size}
        color={color ?? (filled ? colors.accent : colors.text)}
      />
    </Pressable>
  );
}
const buttonStyles = StyleSheet.create({
  base: {
    minHeight: touch,
    paddingHorizontal: space.lg,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  small: {
    minHeight: 34,
    paddingHorizontal: space.md,
    borderRadius: radius.sm,
  },
  block: { alignSelf: "stretch" },
  label: { fontSize: 15, fontWeight: "600" },
  smallLabel: { fontSize: 13 },
  icon: {
    width: touch,
    height: touch,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
});

// ── 입력 ─────────────────────────────────────────────────────
export function Input(props: React.ComponentProps<typeof TextInput>) {
  const [focused, setFocused] = useState(false);
  return (
    <TextInput
      placeholderTextColor={colors.subtle}
      selectionColor={colors.accent}
      {...props}
      onFocus={(e) => {
        setFocused(true);
        props.onFocus?.(e);
      }}
      onBlur={(e) => {
        setFocused(false);
        props.onBlur?.(e);
      }}
      style={[
        styles.input,
        focused && { borderColor: colors.accent },
        props.style,
      ]}
    />
  );
}
/** 돋보기 아이콘과 지우기 버튼이 있는 검색창. */
export function SearchInput({
  value,
  onChangeText,
  placeholder = "검색",
  containerStyle,
  ...rest
}: Omit<
  React.ComponentProps<typeof TextInput>,
  "value" | "onChangeText" | "style"
> & {
  value: string;
  onChangeText: (v: string) => void;
  containerStyle?: StyleProp<ViewStyle>;
}) {
  const { t } = useApp();
  const [focused, setFocused] = useState(false);
  return (
    <View
      style={[
        inputStyles.search,
        focused && { borderColor: colors.accent },
        containerStyle,
      ]}
    >
      <Ionicons name="search" size={18} color={colors.subtle} />
      <TextInput
        placeholderTextColor={colors.subtle}
        selectionColor={colors.accent}
        returnKeyType="search"
        {...rest}
        value={value}
        onChangeText={onChangeText}
        placeholder={t(placeholder)}
        onFocus={(e) => {
          setFocused(true);
          rest.onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          rest.onBlur?.(e);
        }}
        style={inputStyles.searchField}
      />
      {!!value && (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("지우기")}
          onPress={() => onChangeText("")}
          hitSlop={10}
        >
          <Ionicons name="close-circle" size={18} color={colors.subtle} />
        </Pressable>
      )}
    </View>
  );
}
const inputStyles = StyleSheet.create({
  search: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    minHeight: 48,
    paddingHorizontal: 14,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    marginBottom: 10,
  },
  searchField: {
    flex: 1,
    color: colors.text,
    fontSize: 15,
    paddingVertical: 10,
  },
});

// ── 선택 ─────────────────────────────────────────────────────
export function Chip({
  label,
  selected = false,
  onPress,
  icon,
  onRemove,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  icon?: IconName;
  /** 지정하면 오른쪽에 × 버튼을 붙인다(적용된 필터 표시용). */
  onRemove?: () => void;
}) {
  const { t } = useApp();
  const fg = selected ? colors.accent : colors.text;
  return (
    <Pressable
      accessibilityRole={onPress ? "button" : "text"}
      accessibilityState={{ selected }}
      disabled={!onPress}
      onPress={() => {
        tapFeedback("selection");
        onPress?.();
      }}
      style={({ pressed }) => [
        chipStyles.chip,
        selected && chipStyles.selected,
        pressed && { opacity: 0.8 },
      ]}
    >
      {icon && <Ionicons name={icon} size={14} color={fg} />}
      <Text style={[chipStyles.label, { color: fg }]} numberOfLines={1}>
        {t(label)}
      </Text>
      {onRemove && (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${t(label)} ${t("지우기")}`}
          onPress={onRemove}
          hitSlop={10}
        >
          <Ionicons name="close" size={14} color={fg} />
        </Pressable>
      )}
    </Pressable>
  );
}
const chipStyles = StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    minHeight: 36,
    paddingHorizontal: 14,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
  },
  selected: { borderColor: colors.accent, backgroundColor: colors.accentSoft },
  label: { fontSize: 14, fontWeight: "600" },
});
/** 여러 선택지 중 하나. 칩 형태로 줄바꿈하며 나열한다. */
export function Choices({
  values,
  value,
  onChange,
}: {
  values: { key: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <View
      style={[styles.row, { marginBottom: 10 }]}
      accessibilityRole="radiogroup"
    >
      {values.map((item) => (
        <Chip
          key={item.key}
          label={item.label}
          selected={item.key === value}
          onPress={() => onChange(item.key)}
        />
      ))}
    </View>
  );
}
/** 2~4개의 짧은 선택지를 같은 폭으로 나눈 전환 컨트롤. */
export function Segmented({
  values,
  value,
  onChange,
}: {
  values: { key: string; label: string; icon?: IconName }[];
  value: string;
  onChange: (v: string) => void;
}) {
  const { t } = useApp();
  return (
    <View style={segmentStyles.track} accessibilityRole="tablist">
      {values.map((item) => {
        const selected = item.key === value;
        return (
          <Pressable
            key={item.key}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => {
              if (!selected) tapFeedback("selection");
              onChange(item.key);
            }}
            style={[segmentStyles.segment, selected && segmentStyles.selected]}
          >
            {item.icon && (
              <Ionicons
                name={item.icon}
                size={16}
                color={selected ? colors.onAccent : colors.muted}
              />
            )}
            <Text
              numberOfLines={1}
              style={[
                segmentStyles.label,
                selected && { color: colors.onAccent },
              ]}
            >
              {t(item.label)}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
const segmentStyles = StyleSheet.create({
  track: {
    flexDirection: "row",
    padding: 3,
    gap: 3,
    borderRadius: radius.md,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    marginBottom: space.md,
  },
  segment: {
    flex: 1,
    minHeight: 38,
    borderRadius: radius.sm + 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingHorizontal: space.sm,
  },
  selected: { backgroundColor: colors.accent },
  label: { color: colors.muted, fontSize: 14, fontWeight: "600" },
});

// ── 목록 ─────────────────────────────────────────────────────
/** 제목이 붙은 둥근 묶음. 안에 <ListRow>를 넣으면 행 사이에 구분선이 생긴다. */
export function ListSection({
  title,
  footer,
  children,
}: {
  title?: string;
  footer?: string;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  const rows = React.Children.toArray(children).filter(Boolean);
  return (
    <View style={{ marginBottom: space.xl }}>
      {!!title && <Text style={listStyles.sectionTitle}>{t(title)}</Text>}
      <View style={listStyles.section}>
        {rows.map((row, index) => (
          <React.Fragment key={index}>
            {index > 0 && <View style={listStyles.divider} />}
            {row}
          </React.Fragment>
        ))}
      </View>
      {!!footer && <Text style={listStyles.footer}>{t(footer)}</Text>}
    </View>
  );
}
export function ListRow({
  title,
  subtitle,
  value,
  icon,
  onPress,
  right,
  danger = false,
  chevron,
}: {
  title: string;
  subtitle?: string;
  /** 오른쪽에 흐리게 표시하는 현재 값. */
  value?: string;
  icon?: IconName;
  onPress?: () => void;
  right?: React.ReactNode;
  danger?: boolean;
  /** 기본값: onPress가 있으면 표시. */
  chevron?: boolean;
}) {
  const { t } = useApp();
  const tint = danger ? colors.danger : colors.text;
  const content = (
    <>
      {icon && (
        <View
          style={[
            listStyles.iconWrap,
            danger && { backgroundColor: colors.dangerSoft },
          ]}
        >
          <Ionicons
            name={icon}
            size={18}
            color={danger ? colors.danger : colors.accent}
          />
        </View>
      )}
      <View style={{ flex: 1, gap: 2 }}>
        <Text
          style={[type.body, { color: tint, fontWeight: "500" }]}
          numberOfLines={2}
        >
          {t(title)}
        </Text>
        {!!subtitle && (
          <Text style={type.caption} numberOfLines={2}>
            {t(subtitle)}
          </Text>
        )}
      </View>
      {!!value && (
        <Text style={[type.body, { color: colors.muted }]} numberOfLines={1}>
          {t(value)}
        </Text>
      )}
      {right}
      {(chevron ?? !!onPress) && (
        <Ionicons name="chevron-forward" size={18} color={colors.subtle} />
      )}
    </>
  );
  if (!onPress) return <View style={listStyles.row}>{content}</View>;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t(title)}
      onPress={onPress}
      style={({ pressed }) => [
        listStyles.row,
        pressed && { backgroundColor: colors.surface2 },
      ]}
    >
      {content}
    </Pressable>
  );
}
const listStyles = StyleSheet.create({
  sectionTitle: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
    marginLeft: space.xs,
    marginBottom: space.sm,
  },
  section: {
    backgroundColor: colors.panel,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    overflow: "hidden",
  },
  row: {
    minHeight: 52,
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingHorizontal: space.lg,
    paddingVertical: space.md,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.line,
    marginLeft: space.lg,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: radius.sm,
    backgroundColor: colors.accentSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  footer: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 16,
    marginTop: space.sm,
    marginHorizontal: space.xs,
  },
});

// ── 상태 표시 ─────────────────────────────────────────────────
/** 목록이 비었거나 불러오지 못했을 때 보여 주는 안내. */
export function EmptyState({
  icon = "file-tray-outline",
  title,
  description,
  action,
}: {
  icon?: IconName;
  title: string;
  description?: string;
  action?: { label: string; onPress: () => void; icon?: IconName };
}) {
  const { t } = useApp();
  return (
    <View style={stateStyles.empty}>
      <View style={stateStyles.emptyIcon}>
        <Ionicons name={icon} size={28} color={colors.accent} />
      </View>
      <Text style={[type.heading, { textAlign: "center" }]}>{t(title)}</Text>
      {!!description && (
        <Text style={[type.caption, { textAlign: "center", fontSize: 13 }]}>
          {t(description)}
        </Text>
      )}
      {action && (
        <Button
          label={action.label}
          icon={action.icon}
          variant="primary"
          onPress={action.onPress}
          style={{ marginTop: space.sm }}
        />
      )}
    </View>
  );
}
/** 불러오는 동안 자리를 잡아 두는 깜박이는 상자. */
export function Skeleton({
  width = "100%",
  height = 16,
  rounded = radius.sm,
  style,
}: {
  width?: number | `${number}%`;
  height?: number | `${number}%`;
  rounded?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const pulse = useRef(new Animated.Value(0.45)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 0.9,
          duration: 700,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0.45,
          duration: 700,
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  return (
    <Animated.View
      style={[
        {
          width,
          height,
          borderRadius: rounded,
          backgroundColor: colors.surface2,
          opacity: pulse,
        },
        style,
      ]}
    />
  );
}
/** 작은 상태 배지(공개 여부, 진행 상태 등). */
export function Badge({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "accent" | "success" | "danger";
}) {
  const { t } = useApp();
  const palette = {
    neutral: [colors.surface2, colors.muted],
    accent: [colors.accentSoft, colors.accent],
    success: ["rgba(127, 209, 166, 0.14)", colors.success],
    danger: [colors.dangerSoft, colors.danger],
  }[tone];
  return (
    <View style={[stateStyles.badge, { backgroundColor: palette[0] }]}>
      <Text style={[stateStyles.badgeText, { color: palette[1] }]}>
        {t(label)}
      </Text>
    </View>
  );
}
const stateStyles = StyleSheet.create({
  empty: {
    alignItems: "center",
    gap: space.sm,
    paddingVertical: space.xxl,
    paddingHorizontal: space.xl,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: space.xs,
  },
  badge: {
    alignSelf: "flex-start",
    borderRadius: radius.pill,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  badgeText: { fontSize: 11, fontWeight: "700" },
});

export function CachedImage({
  url,
  large = false,
  height = 130,
  fill = false,
  transparent = false,
  contentPosition = "center",
}: {
  url: string;
  large?: boolean;
  height?: number | `${number}%`;
  fill?: boolean;
  transparent?: boolean;
  contentPosition?: "center" | "left center" | "right center";
}) {
  const [source, setSource] = useState(url ? absoluteUrl(url) : "");
  useEffect(() => {
    let live = true;
    setSource(url ? absoluteUrl(url) : "");
    cachedImage(url, !large)
      .then((path) => {
        if (live) setSource(path);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [url, large]);
  return source ? (
    <Image
      source={source}
      contentFit="contain"
      contentPosition={contentPosition}
      style={{
        width: large || fill ? "100%" : 94,
        height,
        borderRadius: 6,
        backgroundColor: transparent ? "transparent" : colors.panel,
      }}
    />
  ) : (
    <Skeleton width={large || fill ? "100%" : 94} height={height} rounded={6} />
  );
}
export function RichText({ text }: { text: string }) {
  return (
    <Markdown
      style={{
        body: { color: colors.text, fontSize: 15, lineHeight: 22 },
        paragraph: { marginTop: 0, marginBottom: 6 },
        link: { color: colors.accent },
        code_inline: { backgroundColor: colors.line, color: colors.text },
        heading1: { fontSize: 22 },
      }}
    >
      {text || ""}
    </Markdown>
  );
}
export function Notice({ text }: { text: string }) {
  const { t } = useApp();
  return text ? (
    <Text style={[styles.muted, { marginVertical: 8 }]}>{t(text)}</Text>
  ) : null;
}

// ── 목록 화면 공통 도구 ─────────────────────────────────────────
/** 필터 화면을 여는 버튼. 적용된 조건 수를 배지로 보여 준다. */
export function FilterButton({
  count,
  onPress,
}: {
  count: number;
  onPress: () => void;
}) {
  const { t } = useApp();
  const active = count > 0;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t("필터") + (active ? " " + String(count) : "")}
      onPress={onPress}
      style={({ pressed }) => [
        toolStyles.filter,
        active && toolStyles.filterActive,
        pressed && { opacity: 0.8 },
      ]}
    >
      <Ionicons
        name="options-outline"
        size={18}
        color={active ? colors.accent : colors.text}
      />
      <Text
        style={[toolStyles.filterLabel, active && { color: colors.accent }]}
      >
        {t("필터")}
      </Text>
      {active && (
        <View style={toolStyles.count}>
          <Text style={toolStyles.countText}>{count}</Text>
        </View>
      )}
    </Pressable>
  );
}
/** − 값 + 형태의 수량 조절기. */
export function Stepper({
  value,
  onChange,
  min = 0,
  max,
  label,
  disabled = false,
}: {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  /** 화면 낭독기용 이름. */
  label: string;
  disabled?: boolean;
}) {
  const { t } = useApp();
  const canDown = !disabled && value > min;
  const canUp = !disabled && (max === undefined || value < max);
  const step = (next: number) => {
    tapFeedback("selection");
    onChange(next);
  };
  return (
    <View
      accessible
      accessibilityRole="adjustable"
      accessibilityLabel={t(label)}
      accessibilityValue={{ now: value, min, max }}
      accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
      onAccessibilityAction={(event) => {
        if (event.nativeEvent.actionName === "increment" && canUp)
          step(value + 1);
        if (event.nativeEvent.actionName === "decrement" && canDown)
          step(value - 1);
      }}
      style={[toolStyles.stepper, disabled && { opacity: 0.4 }]}
    >
      <Pressable
        importantForAccessibility="no"
        disabled={!canDown}
        onPress={() => step(value - 1)}
        hitSlop={4}
        style={({ pressed }) => [
          toolStyles.stepButton,
          pressed && { backgroundColor: colors.line },
        ]}
      >
        <Ionicons
          name="remove"
          size={18}
          color={canDown ? colors.text : colors.subtle}
        />
      </Pressable>
      <Text style={toolStyles.stepValue}>{value}</Text>
      <Pressable
        importantForAccessibility="no"
        disabled={!canUp}
        onPress={() => step(value + 1)}
        hitSlop={4}
        style={({ pressed }) => [
          toolStyles.stepButton,
          pressed && { backgroundColor: colors.line },
        ]}
      >
        <Ionicons
          name="add"
          size={18}
          color={canUp ? colors.accent : colors.subtle}
        />
      </Pressable>
    </View>
  );
}
/** 화면 오른쪽 아래에 떠 있는 주요 동작 버튼. */
export function Fab({
  label,
  icon,
  onPress,
  bottom = space.xl,
}: {
  label: string;
  icon: IconName;
  onPress: () => void;
  bottom?: number;
}) {
  const { t } = useApp();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t(label)}
      onPress={() => {
        tapFeedback();
        onPress();
      }}
      style={({ pressed }) => [
        toolStyles.fab,
        { bottom },
        pressed && pressedStyle,
      ]}
    >
      <Ionicons name={icon} size={22} color={colors.onAccent} />
      <Text style={toolStyles.fabLabel}>{t(label)}</Text>
    </Pressable>
  );
}
const toolStyles = StyleSheet.create({
  filter: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    minHeight: touch,
    paddingHorizontal: 14,
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  filterActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accentSoft,
  },
  filterLabel: { color: colors.text, fontSize: 15, fontWeight: "600" },
  count: {
    minWidth: 20,
    height: 20,
    paddingHorizontal: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  countText: { color: colors.onAccent, fontSize: 12, fontWeight: "800" },
  stepper: {
    flexDirection: "row",
    alignItems: "center",
    borderRadius: radius.md,
    backgroundColor: colors.surface2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  stepButton: {
    width: 38,
    height: 38,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  stepValue: {
    minWidth: 26,
    textAlign: "center",
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
    fontVariant: ["tabular-nums"],
  },
  fab: {
    position: "absolute",
    right: space.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    minHeight: 52,
    paddingHorizontal: 20,
    borderRadius: radius.pill,
    backgroundColor: colors.accent,
    elevation: 6,
    shadowColor: "#000",
    shadowOpacity: 0.35,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
  },
  fabLabel: { color: colors.onAccent, fontSize: 15, fontWeight: "700" },
});
