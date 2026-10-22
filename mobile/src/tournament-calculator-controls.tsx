import React, { useState } from "react";
import { Alert, Text, View } from "react-native";
import { useApp } from "./provider";
import type { Action, CalcState } from "./types";
import { Button, Notice, styles, colors } from "./ui";
import { LandscapeModal } from "./calculator-board";

export function TournamentCalculatorControls({
  state,
  now,
  busy,
  connected,
  onAction,
  onResults,
}: {
  state: CalcState;
  now: number;
  busy: boolean;
  connected: boolean;
  onAction: (action: Action) => Promise<void>;
  onResults: () => void;
}) {
  const { t } = useApp();
  const [open, setOpen] = useState(false);
  const set = state.set;
  const left = state.round_timer?.ends_at
    ? Math.max(
        0,
        Math.ceil((Date.parse(state.round_timer.ends_at) - now) / 1000),
      )
    : 0;
  const confirmed =
    set?.report_side === "p1" ? set.player1_confirmed : set?.player2_confirmed;
  const winner =
    set?.winner_candidate === "p1"
      ? state.players.p1.name
      : set?.winner_candidate === "p2"
        ? state.players.p2.name
        : "";
  return (
    <View style={{ gap: 4 }}>
      <Text style={[styles.muted, { textAlign: "center" }]}>
        {t("세트")} {set?.current_number} · {set?.score.p1} : {set?.score.p2}
      </Text>
      <Text
        style={{
          color: left ? colors.accent : colors.danger,
          textAlign: "center",
          fontSize: 12,
        }}
      >
        {t("라운드")} {Math.floor(left / 60)}:
        {String(left % 60).padStart(2, "0")}
      </Text>
      <Button label="경기 · 세트 결과" onPress={() => setOpen(true)} />
      <LandscapeModal
        visible={open}
        title={t("경기 · 세트 결과")}
        onClose={() => setOpen(false)}
      >
        <Text style={styles.title}>
          {state.tournament?.name} · R{state.tournament?.round_number} ·{" "}
          {state.tournament?.table}
        </Text>
        <Text style={styles.text}>
          {state.players.p1.name} {set?.score.p1} : {set?.score.p2}{" "}
          {state.players.p2.name}
        </Text>
        <Notice
          text={
            state.tournament?.match_status === "reported"
              ? "결과 제출 완료"
              : !left && !state.sudden_death
                ? "라운드 시간이 종료되었습니다. 운영자에게 문의해주세요."
                : "양쪽 참가자가 세트 결과를 확인하면 다음 세트 또는 경기 결과에 반영됩니다."
          }
        />
        <View style={[styles.row, { marginVertical: 8 }]}>
          <Text style={styles.text}>
            {state.players.p1.name}:{" "}
            {t(set?.player1_confirmed ? "확인 완료" : "확인 대기")}
          </Text>
          <Text style={styles.text}>
            {state.players.p2.name}:{" "}
            {t(set?.player2_confirmed ? "확인 완료" : "확인 대기")}
          </Text>
        </View>
        {!!winner && (
          <Text style={styles.text}>
            {t("세트 승자")}: {winner}
          </Text>
        )}
        {!winner && set?.can_report && (
          <Notice text="HP 또는 서든 데스 결과로 승자가 정해진 뒤 확인할 수 있습니다." />
        )}
        <View style={[styles.row, { marginTop: 12, marginBottom: 20 }]}>
          <Button
            label={confirmed ? "내 확인 완료" : "세트 결과 확인"}
            disabled={
              !connected || busy || !set?.can_report || !winner || !!confirmed
            }
            onPress={() =>
              Alert.alert(t("세트 결과 확인"), `${t("세트 승자")}: ${winner}`, [
                { text: t("취소"), style: "cancel" },
                {
                  text: t("확인"),
                  onPress: () => void onAction({ action: "report_set" }),
                },
              ])
            }
          />
          <Button label="대회로 돌아가기" onPress={onResults} />
        </View>
        {(["p1", "p2"] as const).map((target) => {
          const choice = state.character_choices?.[target];
          if (!choice?.can_choose) return null;
          return (
            <View key={target} style={{ marginBottom: 16 }}>
              <Text style={[styles.text, { marginBottom: 8 }]}>
                {state.players[target].name} · {t("캐릭터 선택")}
              </Text>
              <View style={styles.row}>
                {choice.options.map((c) => (
                  <Button
                    key={c.id}
                    label={`${state.players[target].character?.id === c.id ? "✓ " : ""}${c.name}`}
                    disabled={busy || !connected || !state.can_control}
                    onPress={() =>
                      void onAction({
                        action: "character",
                        target,
                        character_id: c.id,
                      })
                    }
                  />
                ))}
              </View>
            </View>
          );
        })}
      </LandscapeModal>
    </View>
  );
}
