import React, { useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useApp } from "../../src/provider";
import { request } from "../../src/api";
import { saveShared } from "../../src/shared";
import { userMessage } from "../../src/errors";
import { useCalculatorEntry } from "../../src/calculator-entry";
import {
  useTournamentResource,
  tournamentStatus,
  type TournamentDetail,
  type TournamentMatch,
} from "../../src/tournaments";
import { TournamentResult } from "../../src/tournament-result";
import { deckDescription } from "../../src/deck-display";
import { Button, Notice, styles } from "../../src/ui";

export default function MyTournament() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user, online, scope, language, t } = useApp();
  const ownerRef = useRef(user?.id);
  ownerRef.current = user?.id;
  const { data, message, busy, refresh } =
    useTournamentResource<TournamentDetail>(`/tournaments/${id}`);
  const [report, setReport] = useState<{
    scope: string;
    match: TournamentMatch;
  } | null>(null);
  const [opening, setOpening] = useState(false),
    [error, setError] = useState("");
  const { chooseUi, entrySheet } = useCalculatorEntry();
  async function open(match: TournamentMatch) {
    if (!user || !online || opening) return;
    const owner = user.id;
    const ui = await chooseUi();
    if (!ui || ownerRef.current !== owner) return;
    setOpening(true);
    setError("");
    try {
      const result = await request(
        `/tournaments/${id}/matches/${match.id}/calculator?language=${language}`,
        { method: "POST" },
        true,
        false,
        owner,
      );
      if (ownerRef.current !== owner) return;
      await saveShared({
        view_token: result.view_token,
        control_token: "",
        tournament: {
          tournament_id: Number(id),
          match_id: match.id,
          user_id: owner,
        },
      });
      if (ownerRef.current === owner)
        router.push({
          pathname: "/calculator",
          params: { tournament: "1", ui },
        });
    } catch (err) {
      setError(userMessage(err));
    } finally {
      setOpening(false);
    }
  }
  if (!user)
    return (
      <View style={styles.screen}>
        <Notice text="참가한 대회를 확인하려면 로그인해주세요." />
        <Button label="로그인" onPress={() => router.push("/settings")} />
      </View>
    );
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      {entrySheet}
      {report?.scope === scope && (
        <TournamentResult
          key={`${scope}:${report.match.id}`}
          match={report.match}
          onClose={() => setReport(null)}
          onSaved={refresh}
        />
      )}
      <Text style={styles.title}>{data?.name || t("내 대회")}</Text>
      <Button label="새로고침" onPress={refresh} disabled={busy} />
      <Notice text={message || error} />
      {data && (
        <>
          <Text style={styles.text}>
            {t(tournamentStatus[data.status] || data.status)} ·{" "}
            {data.participant_name}
          </Text>
          <Text style={[styles.muted, { marginVertical: 8 }]}>
            {new Date(data.event_date).toLocaleString(language)}
            {data.venue ? ` · ${data.venue}` : ""}
          </Text>
          <Text style={[styles.title, { marginTop: 18 }]}>{t("내 경기")}</Text>
          {!data.matches.length && (
            <Notice text="아직 배정된 경기가 없습니다." />
          )}
          {data.matches.map((match) => (
            <View key={match.id} style={styles.panel}>
              <Text style={[styles.title, { fontSize: 18 }]}>
                R{match.round_number} · {match.table}
              </Text>
              <Text style={styles.text}>
                {match.players.p1.name} {match.score.p1} : {match.score.p2}{" "}
                {match.players.p2?.name || "BYE"}
              </Text>
              <Notice
                text={
                  match.is_bye
                    ? "부전승"
                    : match.status === "reported"
                      ? "결과 제출 완료"
                      : match.round_status === "finished"
                        ? "라운드 종료"
                        : "결과 대기"
                }
              />
              <Text style={styles.muted}>
                {match.set_count} {t("세트")} · {t("라운드 종료 시각")}:{" "}
                {new Date(match.round_ends_at).toLocaleTimeString(language)}
              </Text>
              <View style={[styles.row, { marginTop: 12 }]}>
                {match.can_open_calculator && (
                  <Button
                    label="경기 계산기"
                    disabled={!online || opening}
                    onPress={() => open(match)}
                  />
                )}
                {match.can_report && (
                  <Button
                    label="경기 결과 제출"
                    disabled={!online}
                    onPress={() => setReport({ scope, match })}
                  />
                )}
              </View>
            </View>
          ))}
          {!!data.decks.length && (
            <>
              <Text style={styles.title}>{t("제출한 덱")}</Text>
              {data.decks.map((d) => (
                <View key={d.slot} style={[styles.row, { marginBottom: 8 }]}>
                  <Text style={styles.text}>
                    #{d.slot} {d.name}
                  </Text>
                  <Button
                    label="보기"
                    onPress={() =>
                      router.push({
                        pathname: "/deck/[id]",
                        params: { id: String(d.id) },
                      })
                    }
                  />
                </View>
              ))}
            </>
          )}
          {!!data.description && (
            <View style={styles.panel}>
              <Text style={styles.text}>
                {deckDescription(data.description)}
              </Text>
            </View>
          )}
        </>
      )}
    </ScrollView>
  );
}
