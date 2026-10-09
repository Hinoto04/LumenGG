import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  Pressable,
  TextInput,
  StyleSheet,
  FlatList,
} from "react-native";
import { Image } from "expo-image";
import Markdown from "react-native-markdown-display";
import { useApp } from "./provider";
import { cachedImage } from "./catalog";
import { absoluteUrl } from "./api";
export const colors = {
  bg: "#111111",
  panel: "#1b1b1b",
  line: "#303030",
  text: "#f4f1ea",
  muted: "#b8b0a4",
  accent: "#e0b45b",
  danger: "#ff8d9b",
};
export const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  panel: {
    backgroundColor: colors.panel,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.line,
  },
  row: { flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "700",
    marginBottom: 12,
  },
  text: { color: colors.text, fontSize: 15 },
  muted: { color: colors.muted, fontSize: 12 },
  button: {
    backgroundColor: colors.line,
    borderRadius: 9,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  buttonText: { color: colors.accent, fontWeight: "600" },
  input: {
    color: colors.text,
    backgroundColor: colors.panel,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 9,
    padding: 12,
    marginBottom: 10,
  },
});
export function Button({
  label,
  onPress,
  disabled = false,
  danger = false,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  const { t } = useApp();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t(label)}
      disabled={disabled}
      onPress={onPress}
      style={[styles.button, { opacity: disabled ? 0.4 : 1 }]}
    >
      <Text style={[styles.buttonText, danger && { color: colors.danger }]}>
        {t(label)}
      </Text>
    </Pressable>
  );
}
export function Input(props: React.ComponentProps<typeof TextInput>) {
  return (
    <TextInput
      placeholderTextColor={colors.muted}
      {...props}
      style={[styles.input, props.style]}
    />
  );
}
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
    <View style={[styles.row, { marginBottom: 10 }]}>
      {values.map((item) => (
        <Pressable
          key={item.key}
          onPress={() => onChange(item.key)}
          style={[
            styles.button,
            { backgroundColor: item.key === value ? "#4b3d24" : colors.panel },
          ]}
        >
          <Text style={styles.buttonText}>{item.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}
export function CachedImage({
  url,
  large = false,
  height = 130,
  fill = false,
}: {
  url: string;
  large?: boolean;
  height?: number;
  fill?: boolean;
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
      style={{
        width: large || fill ? "100%" : 94,
        height,
        borderRadius: 6,
        backgroundColor: colors.panel,
      }}
    />
  ) : (
    <View
      style={{
        width: large || fill ? "100%" : 94,
        height,
        backgroundColor: colors.line,
      }}
    />
  );
}
export function RichText({ text }: { text: string }) {
  return (
    <Markdown
      style={{
        body: { color: colors.text, fontSize: 15 },
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
