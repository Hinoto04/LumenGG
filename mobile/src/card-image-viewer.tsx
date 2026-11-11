import React from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { CachedImage, IconButton, colors, space } from "./ui";

/** 카드 이미지를 화면 가득 보여 주는 오버레이. 아무 곳이나 누르면 닫힌다. */
export function CardImageViewer({
  url,
  title,
  onClose,
}: {
  /** 비어 있으면 닫힌 상태다. */
  url: string;
  title?: string;
  onClose: () => void;
}) {
  const insets = useSafeAreaInsets();
  return (
    <Modal
      visible={!!url}
      transparent
      statusBarTranslucent
      animationType="fade"
      onRequestClose={onClose}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={title}
        onPress={onClose}
        style={[
          viewerStyles.backdrop,
          { paddingTop: insets.top + 56, paddingBottom: insets.bottom + 24 },
        ]}
      >
        {!!url && <CachedImage url={url} large height="100%" transparent />}
      </Pressable>
      <View style={[viewerStyles.header, { top: insets.top + space.sm }]}>
        <Text numberOfLines={1} style={viewerStyles.title}>
          {title}
        </Text>
        <IconButton icon="close" label="닫기" onPress={onClose} filled />
      </View>
    </Modal>
  );
}

const viewerStyles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0, 0, 0, 0.92)",
    paddingHorizontal: space.lg,
    alignItems: "center",
    justifyContent: "center",
  },
  header: {
    position: "absolute",
    left: space.lg,
    right: space.sm,
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
  },
  title: { flex: 1, color: colors.text, fontSize: 17, fontWeight: "700" },
});
