import React, { useEffect, useState } from "react";
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { PartySupply } from "./party";
import { supplyCombo } from "./party-supply";
import { Button } from "./ui";

export function PartySupplyChoice({
  crate,
  visible,
  visit,
  locked,
  onAttack,
  onSkip,
}: {
  crate: PartySupply | null;
  visible: boolean;
  visit: string;
  locked: boolean;
  onAttack: (combo: { speeds: number[]; damage: number }) => void;
  onSkip: () => void;
}) {
  const [speeds, setSpeeds] = useState(""),
    [damage, setDamage] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    setSpeeds("");
    setDamage("");
    setError("");
  }, [visit, crate?.id]);
  return (
    <Modal
      visible={visible && !!crate}
      transparent
      animationType="fade"
      onRequestClose={() => !locked && onSkip()}
    >
      <View style={s.backdrop}>
        <ScrollView
          contentContainerStyle={s.center}
          keyboardShouldPersistTaps="handled"
        >
          <View style={s.panel} accessibilityViewIsModal>
            <Text style={s.kicker}>SUPPLY CRATE</Text>
            <Text style={s.title}>보급함을 만났어요</Text>
            <Text style={s.crate}>▣</Text>
            <Text style={s.title}>
              ♥ {crate?.hp} / {crate?.max_hp}
            </Text>
            <Text style={s.text}>
              실물 카드를 속도 오름차순으로 사용하세요. 장수 제한은 없으며
              사용한 카드는 리스트로 보냅니다.
            </Text>
            <Text style={s.text}>사용한 카드의 속도 순서</Text>
            <TextInput
              accessibilityLabel="사용한 카드의 속도 순서"
              value={speeds}
              onChangeText={setSpeeds}
              placeholder="예: 3, 5, 8"
              placeholderTextColor="#8a9db4"
              style={s.input}
              editable={!locked}
              autoCorrect={false}
            />
            <Text style={s.text}>콤보 보정·효과 적용 후 최종 피해</Text>
            <TextInput
              accessibilityLabel="보급함 최종 피해"
              value={damage}
              onChangeText={setDamage}
              placeholder="예: 800"
              placeholderTextColor="#8a9db4"
              style={s.input}
              keyboardType="number-pad"
              editable={!locked}
            />
            <Text style={s.text}>
              파괴하면 2코인 획득. 피해 보상과 플레이어 기절 보상은 적용되지
              않습니다.
            </Text>
            {!!error && (
              <Text accessibilityRole="alert" style={s.error}>
                {error}
              </Text>
            )}
            <View style={s.actions}>
              <View style={s.action}>
                <Button label="지나가기" disabled={locked} onPress={onSkip} />
              </View>
              <View style={s.action}>
                <Button
                  label="공격 결과 반영"
                  disabled={locked}
                  onPress={() => {
                    try {
                      const combo = supplyCombo(speeds, damage);
                      setError("");
                      onAttack(combo);
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                />
              </View>
            </View>
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}
const s = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "#050b18cc" },
  center: { flexGrow: 1, justifyContent: "center", padding: 18 },
  panel: {
    width: "100%",
    maxWidth: 600,
    alignSelf: "center",
    backgroundColor: "#17283f",
    borderRadius: 22,
    padding: 22,
    gap: 12,
  },
  kicker: {
    color: "#f3c477",
    fontSize: 12,
    fontWeight: "800",
    textAlign: "center",
  },
  title: {
    fontSize: 24,
    color: "#fff",
    fontWeight: "900",
    textAlign: "center",
  },
  crate: { color: "#f3c477", fontSize: 58, textAlign: "center" },
  text: { color: "#d1dfef", fontSize: 14, lineHeight: 21 },
  input: {
    backgroundColor: "#0d1b2e",
    borderColor: "#7391b6",
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    color: "#fff",
    fontSize: 17,
    minHeight: 46,
  },
  error: { color: "#ffa6ad" },
  actions: { flexDirection: "row", gap: 12 },
  action: { flex: 1 },
});
