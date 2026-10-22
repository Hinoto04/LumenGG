import React, { useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { PartyCardVisual, PartyCardPreview } from "./party-card";
import type { PartyItem, PartyState } from "./party";
import { Button, colors, styles } from "./ui";

export type PartyItemChoice = {
  item: string;
  target?: number;
  node?: number;
  value?: number;
};
function ItemArt({
  item,
  large = false,
}: {
  item?: PartyItem;
  large?: boolean;
}) {
  const { width } = useWindowDimensions();
  return (
    <View style={{ alignItems: "center" }}>
      {item?.image ? (
        <PartyCardVisual
          card={item}
          width={large ? Math.min(280, width - 64) : 58}
          compact={!large}
        />
      ) : (
        <View style={s.art} />
      )}
    </View>
  );
}
export function PartyItemPicker({
  state,
  choice,
  disabled,
  onChange,
  onUse,
  onCancel,
}: {
  state: PartyState;
  choice: PartyItemChoice;
  disabled: boolean;
  onChange: (choice: PartyItemChoice) => void;
  onUse: () => void;
  onCancel: () => void;
}) {
  const [preview, setPreview] = useState(false);
  const item = state.board.shop[choice.item];
  if (!item) return null;
  const targets = state.item_targets?.[choice.item] || [];
  const valid =
    item.target === "self" ||
    (item.target === "player" && targets.includes(choice.target ?? -1)) ||
    (item.target === "tile" && targets.includes(choice.node ?? -1)) ||
    (item.target === "number" && !!choice.value);
  return (
    <View style={[styles.panel, { marginTop: 12, gap: 10 }]}>
      {item.target !== "tile" && <ItemArt item={item} large />}
      {(item.target === "tile" || !item.image) && (
        <>
          <Text style={styles.title}>{item.label}</Text>
          <Text style={styles.text}>{item.description}</Text>
        </>
      )}
      {item.target === "tile" && (
        <Button label="카드 보기" onPress={() => setPreview(true)} />
      )}
      <PartyCardPreview
        card={preview ? item : null}
        onClose={() => setPreview(false)}
      />
      {item.target === "player" && (
        <View style={{ gap: 8 }}>
          {!targets.length && (
            <Text style={styles.muted}>
              사거리 안에 선택할 수 있는 상대가 없어요.
            </Text>
          )}
          {targets.map((seat) => {
            const p = state.players.find((p) => p.seat === seat)!;
            return (
              <Button
                key={seat}
                label={`${choice.target === seat ? "✓ " : ""}${p.name} · ♥${p.hp}${p.shielded ? " · 보호막" : ""}`}
                disabled={disabled}
                onPress={() => onChange({ ...choice, target: seat })}
              />
            );
          })}
        </View>
      )}
      {item.target === "number" && (
        <View style={[styles.row, { flexWrap: "wrap" }]}>
          {[1, 2, 3, 4, 5, 6].map((value) => (
            <Button
              key={value}
              label={`${choice.value === value ? "✓ " : ""}${value}`}
              disabled={disabled}
              onPress={() => onChange({ ...choice, value })}
            />
          ))}
        </View>
      )}
      {item.target === "tile" && (
        <Text style={styles.text}>
          {choice.node !== undefined
            ? `${state.board.nodes[choice.node]!.label} 칸 선택됨`
            : "지도에서 주황색으로 표시된 설치 위치를 눌러주세요."}
        </Text>
      )}
      <View style={styles.row}>
        <Button label="취소" disabled={disabled} onPress={onCancel} />
        <Button label="사용" disabled={disabled || !valid} onPress={onUse} />
      </View>
    </View>
  );
}
const s = StyleSheet.create({
  art: {
    height: 54,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.line,
    borderRadius: 10,
    backgroundColor: "#ffffff08",
  },
});
