import React, { useState } from "react";
import { Alert, Modal, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp } from "./provider";
import { request } from "./api";
import { userMessage } from "./errors";
import type { TournamentMatch } from "./tournaments";
import { Button, Choices, Input, Notice, styles } from "./ui";

export function TournamentResult({
  match,
  onClose,
  onSaved,
}: {
  match: TournamentMatch;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const { user, online, t } = useApp();
  const [p1, setP1] = useState(String(match.score.p1)),
    [p2, setP2] = useState(String(match.score.p2));
  const [winner, setWinner] = useState(match.winner || ""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const submit = async () => {
    if (!user || !online || busy) return;
    setBusy(true);
    setMessage("");
    try {
      await request(
        `/tournaments/${match.tournament_id}/matches/${match.id}/report`,
        {
          method: "POST",
          body: JSON.stringify({
            winner,
            player1_score: Number(p1),
            player2_score: Number(p2),
          }),
        },
        true,
        false,
        user.id,
      );
      await onSaved();
      onClose();
    } catch (err) {
      setMessage(userMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      visible
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={() => {
        if (!busy) onClose();
      }}
    >
      <SafeAreaView style={styles.screen}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingBottom: 32 }}
        >
          <Text style={styles.title}>{t("경기 결과 제출")}</Text>
          <Text style={styles.muted}>
            R{match.round_number} · {match.table} · {match.set_count}{" "}
            {t("세트")}
          </Text>
          <Notice text="상대와 확인한 경기 결과를 제출해주세요. 제출 후에는 직접 수정할 수 없습니다." />
          <Text style={[styles.text, { marginTop: 12 }]}>
            {match.players.p1.name}
            {match.me === "p1" ? ` (${t("나")})` : ""}
          </Text>
          <Input
            accessibilityLabel={t("플레이어1 세트 점수")}
            value={p1}
            onChangeText={setP1}
            keyboardType="number-pad"
          />
          <Text style={styles.text}>
            {match.players.p2?.name}
            {match.me === "p2" ? ` (${t("나")})` : ""}
          </Text>
          <Input
            accessibilityLabel={t("플레이어2 세트 점수")}
            value={p2}
            onChangeText={setP2}
            keyboardType="number-pad"
          />
          <Text style={[styles.text, { marginBottom: 8 }]}>{t("승자")}</Text>
          <Choices
            value={winner}
            onChange={setWinner}
            values={[
              { key: "p1", label: match.players.p1.name },
              { key: "p2", label: match.players.p2?.name || "" },
              ...(match.stage === "swiss"
                ? [{ key: "draw", label: t("무승부") }]
                : []),
            ]}
          />
          <Notice text={message} />
          {!online && (
            <Notice text="연결이 끊겼습니다. 결과는 온라인에서 제출해주세요." />
          )}
          <View style={styles.row}>
            <Button label="취소" onPress={onClose} disabled={busy} />
            <Button
              label="결과 제출"
              disabled={
                !online ||
                busy ||
                !winner ||
                !/^\d+$/.test(p1) ||
                !/^\d+$/.test(p2)
              }
              onPress={() =>
                Alert.alert(
                  t("경기 결과 제출"),
                  `${match.players.p1.name} ${p1} : ${p2} ${match.players.p2?.name}\n${t("승자")}: ${winner === "draw" ? t("무승부") : match.players[winner as "p1" | "p2"]?.name}`,
                  [
                    { text: t("취소"), style: "cancel" },
                    { text: t("결과 제출"), onPress: submit },
                  ],
                )
              }
            />
          </View>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  );
}
