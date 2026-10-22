import React, { useState } from "react";
import { Image } from "expo-image";
import {
  Modal,
  Pressable,
  ScrollView,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { absoluteUrl } from "./api";
import type { PartyCardDisplay } from "./party";

export function PartyCardVisual({
  card,
  width,
  compact = false,
}: {
  card: PartyCardDisplay;
  width?: number;
  compact?: boolean;
}) {
  const [measured, setMeasured] = useState(width || 260);
  const box = card.effect_box || {
    left: 0.1,
    top: 60 / 88,
    width: 0.8,
    height: 20.2 / 88,
    fontPt: 8.8,
    lineHeight: 1.25,
  };
  const font = measured * (box.fontPt || 8.8) * 0.005609;
  return (
    <View
      accessible
      accessibilityLabel={`${card.label} · ${card.description}`}
      pointerEvents={compact ? "none" : "auto"}
      onLayout={(event) => setMeasured(event.nativeEvent.layout.width)}
      style={{
        position: "relative",
        width: width || "100%",
        aspectRatio: 63 / 88,
        flexShrink: 0,
      }}
    >
      <View
        style={{
          position: "absolute",
          left: "2.41611%",
          right: "2.41611%",
          top: "1.73077%",
          bottom: "1.73077%",
          overflow: "hidden",
          borderRadius: (measured * 30) / 745,
        }}
      >
        <View
          style={{
            position: "absolute",
            left: `${(-18 / 709) * 100}%`,
            top: `${(-18 / 1004) * 100}%`,
            width: `${(745 / 709) * 100}%`,
            height: `${(1040 / 1004) * 100}%`,
          }}
        >
          {!!card.image && (
            <Image
              source={{ uri: absoluteUrl(card.image) }}
              contentFit="fill"
              style={{ position: "absolute", inset: 0 }}
            />
          )}
          <View
            style={{
              position: "absolute",
              left: `${box.left * 100}%`,
              top: `${box.top * 100}%`,
              width: `${box.width * 100}%`,
              height: `${box.height * 100}%`,
              overflow: "hidden",
            }}
          >
            <ScrollView
              scrollEnabled={!compact}
              contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}
              showsVerticalScrollIndicator={false}
            >
              <Text
                style={{
                  fontSize: font,
                  lineHeight: font * (box.lineHeight || 1.25),
                  fontWeight: "500",
                  color: "#1b2b3a",
                }}
              >
                {card.description}
              </Text>
            </ScrollView>
          </View>
        </View>
      </View>
    </View>
  );
}

export function PartyCardPreview({
  card,
  onClose,
}: {
  card: PartyCardDisplay | null;
  onClose: () => void;
}) {
  const { width, height } = useWindowDimensions();
  return (
    <Modal
      visible={!!card}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View
        accessibilityViewIsModal
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          padding: 24,
          backgroundColor: "#102839ed",
        }}
      >
        {!!card && (
          <PartyCardVisual
            card={card}
            width={Math.min(300, width - 48, ((height - 120) * 63) / 88)}
          />
        )}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="카드 미리보기 닫기"
          onPress={onClose}
          style={{
            marginTop: 12,
            minHeight: 44,
            minWidth: 140,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 12,
            borderWidth: 1,
            borderColor: "#cde9ff",
            backgroundColor: "#294c6d",
          }}
        >
          <Text style={{ fontSize: 16, color: "#fff" }}>닫기</Text>
        </Pressable>
      </View>
    </Modal>
  );
}
