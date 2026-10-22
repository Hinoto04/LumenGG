import React, { useState } from "react";
import {
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { absoluteUrl } from "./api";
import { PartyCardVisual } from "./party-card";
import type { PartyState } from "./party";

export type ArrivalChoiceKind =
  "shop" | "charge" | "camp_gift" | "camp_pass" | "transfer";

export function PartyArrivalChoice({
  state,
  kind,
  disabled,
  onConfirm,
  onCancel,
}: {
  state: PartyState;
  kind: ArrivalChoiceKind;
  disabled: boolean;
  onConfirm: (value: string | number) => void;
  onCancel: () => void;
}) {
  const [selection, setSelection] = useState<string | number | null>(null);
  const { width, height } = useWindowDimensions();
  const player = state.players.find((p) => p.seat === state.me?.seat)!;
  const cardWidth = Math.min(
    210,
    width - 88,
    Math.max(140, ((height - 300) * 63) / 88),
  );
  const cards = kind === "shop" || kind === "camp_gift";
  const direct = kind === "camp_pass" || kind === "transfer";
  const item =
    cards && typeof selection === "string" ? state.board.shop[selection] : null;
  const target =
    kind === "charge" ? state.players.find((p) => p.seat === selection) : null;
  const canConfirm =
    selection !== null &&
    (kind !== "shop" ||
      (!!item &&
        player.coins >= item.price &&
        (state.me?.items.length || 0) < 3));
  const options =
    kind === "camp_gift"
      ? state.camp_gift?.items || []
      : direct
        ? []
        : kind === "shop"
          ? state.shop_offers
          : state.players
              .filter((p) => p.seat !== player.seat && p.hp > 0 && !p.cloaked)
              .map((p) => p.seat);
  const title = {
    shop: "어떤 아이템을 살까요?",
    charge: "누구에게 돌격할까요?",
    camp_gift: "승점 획득! 보상을 골라주세요",
    camp_pass: "거점에 머무를까요?",
    transfer: "교체 지점에 도착했어요",
  }[kind];
  const stopDetail =
    player.crystals >= 3
      ? "승점을 모두 구매했어요"
      : state.camp_purchase_done
        ? "이번 턴 승점 구매 완료"
        : `승점 구매까지 앞으로 ${state.camp_stop_shortfall}골드`;
  return (
    <Modal
      transparent
      animationType="fade"
      onRequestClose={() => !disabled && onCancel()}
    >
      <View style={s.backdrop} accessibilityViewIsModal>
        <View style={[s.panel, { maxHeight: height - 60 }]}>
          <Text style={s.eyebrow}>
            {kind === "shop"
              ? "ITEM SHOP"
              : kind === "camp_gift"
                ? "CRYSTAL REWARD"
                : kind === "camp_pass"
                  ? "CAMP"
                  : kind === "transfer"
                    ? "TRANSFER"
                    : "CHARGE"}
          </Text>
          <Text style={s.title}>{title}</Text>
          {direct ? (
            <>
              <Image
                source={{
                  uri: absoluteUrl(
                    state.board.nodes[player.position]!.background_img || "",
                  ),
                }}
                resizeMode="contain"
                style={{
                  width: 130,
                  height: 130,
                  alignSelf: "center",
                  marginVertical: 24,
                }}
              />
              <View style={{ gap: 14 }}>
                <Pressable
                  accessibilityRole="button"
                  disabled={disabled}
                  onPress={onCancel}
                  style={[
                    s.button,
                    { flex: undefined, minHeight: 85 },
                    disabled && s.disabled,
                  ]}
                >
                  <Text style={s.buttonText}>
                    {kind === "camp_pass" ? "이대로 이동" : "여기에 멈추기"}
                  </Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={disabled}
                  onPress={() => onConfirm("confirm")}
                  style={[
                    s.button,
                    s.confirm,
                    { flex: undefined, minHeight: 100 },
                    disabled && s.disabled,
                  ]}
                >
                  <Text style={[s.buttonText, { textAlign: "center" }]}>
                    {kind === "camp_pass"
                      ? `거점에 멈추기\n(${stopDetail})`
                      : "반대편 교체로 이동"}
                  </Text>
                </Pressable>
              </View>
            </>
          ) : (
            <>
              <Text style={s.hint}>
                {kind === "camp_gift"
                  ? "세 아이템 중 하나를 무료로 획득합니다."
                  : kind === "shop"
                    ? `무작위 아이템 3개 · 보유 ${player.coins}코인 · 가방 ${state.me?.items.length}/3`
                    : "상대를 선택한 뒤 확인을 눌러주세요."}
              </Text>
              <ScrollView
                horizontal
                contentContainerStyle={s.options}
                showsHorizontalScrollIndicator
              >
                {options.map((value) => {
                  const entry =
                    cards && typeof value === "string"
                      ? state.board.shop[value]
                      : null;
                  const opponent =
                    !cards && typeof value === "number"
                      ? state.players.find((p) => p.seat === value)
                      : null;
                  return (
                    <Pressable
                      key={value}
                      accessibilityRole="button"
                      accessibilityState={{ selected: selection === value }}
                      accessibilityLabel={
                        entry?.label || `${opponent?.name}에게 돌격`
                      }
                      disabled={disabled}
                      onPress={() => setSelection(value)}
                      style={[
                        s.option,
                        { width: cardWidth + 20 },
                        selection === value && s.selected,
                      ]}
                    >
                      {entry && (
                        <PartyCardVisual
                          card={entry}
                          width={cardWidth}
                          compact
                        />
                      )}
                      {opponent && (
                        <Image
                          source={{
                            uri: absoluteUrl(
                              opponent.character.body_img ||
                                opponent.character.sd_img ||
                                opponent.character.icon_img ||
                                opponent.character.img,
                            ),
                          }}
                          resizeMode="contain"
                          style={{ width: cardWidth, height: cardWidth * 1.3 }}
                        />
                      )}
                      <Text style={s.name}>
                        {entry?.label || opponent?.name}
                      </Text>
                      <Text style={s.price}>
                        {entry
                          ? kind === "camp_gift"
                            ? "무료 획득"
                            : `${entry.price}코인`
                          : `♥${opponent?.hp} · FP ${opponent?.fp}`}
                      </Text>
                    </Pressable>
                  );
                })}
                {!options.length && (
                  <Text style={s.hint}>돌격할 수 있는 상대가 없어요.</Text>
                )}
              </ScrollView>
              <Text style={s.hint}>
                {selection === null
                  ? "선택하지 않고 취소할 수도 있어요."
                  : cards
                    ? !canConfirm
                      ? "코인과 가방 공간을 확인해주세요."
                      : kind === "camp_gift"
                        ? state.me?.items.length === 3
                          ? "획득 후 교체할 아이템을 선택합니다."
                          : `${item?.label} 획득`
                        : `${item?.label} · ${item?.price}코인에 구매`
                    : `${target?.name}의 위치로 이동합니다.`}
              </Text>
              <View style={s.actions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={disabled}
                  onPress={onCancel}
                  style={[s.button, disabled && s.disabled]}
                >
                  <Text style={s.buttonText}>
                    {kind === "camp_gift" ? "받지 않기" : "취소"}
                  </Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityState={{ disabled: disabled || !canConfirm }}
                  disabled={disabled || !canConfirm}
                  onPress={() => selection !== null && onConfirm(selection)}
                  style={[
                    s.button,
                    s.confirm,
                    (disabled || !canConfirm) && s.disabled,
                  ]}
                >
                  <Text style={s.buttonText}>확인</Text>
                </Pressable>
              </View>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
    backgroundColor: "#101e37d9",
  },
  panel: {
    width: "100%",
    maxWidth: 820,
    borderRadius: 24,
    padding: 16,
    backgroundColor: "#1c354f",
    borderWidth: 2,
    borderColor: "#8eb6ce",
  },
  eyebrow: {
    textAlign: "center",
    color: "#9ee5f7",
    fontWeight: "900",
    letterSpacing: 3,
  },
  title: {
    textAlign: "center",
    color: "#fff",
    fontSize: 24,
    fontWeight: "900",
    marginVertical: 8,
  },
  hint: { color: "#c9dce9", textAlign: "center", marginVertical: 10 },
  options: { gap: 12, paddingVertical: 8 },
  option: {
    alignItems: "center",
    padding: 8,
    borderWidth: 2,
    borderColor: "transparent",
    borderRadius: 16,
    backgroundColor: "#ffffff09",
    gap: 6,
  },
  selected: { borderColor: "#ffd885", backgroundColor: "#ffd88520" },
  name: { color: "#fff", fontSize: 18, fontWeight: "800" },
  price: { color: "#ffe09c", fontWeight: "800" },
  actions: { flexDirection: "row", gap: 12 },
  button: {
    flex: 1,
    minHeight: 54,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 14,
    backgroundColor: "#35536e",
    borderWidth: 1,
    borderColor: "#a3bfd1",
  },
  confirm: { backgroundColor: "#99712c", borderColor: "#ffe0a0" },
  disabled: { opacity: 0.4 },
  buttonText: { color: "#fff", fontSize: 21, fontWeight: "900" },
});
