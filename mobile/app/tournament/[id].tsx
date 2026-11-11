import React, { useRef, useState } from "react";
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { router, Stack, useLocalSearchParams } from "expo-router";
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
import {
  Badge,
  Button,
  EmptyState,
  ListRow,
  ListSection,
  Notice,
  Skeleton,
  colors,
  radius,
  space,
  styles,
  type,
} from "../../src/ui";
import { InfoLine, statusTone } from "../../src/tournament-ui";

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
        <EmptyState
          icon="trophy-outline"
          title="참가한 대회를 확인하려면 로그인해주세요."
          action={{
            label: "로그인",
            icon: "log-in-outline",
            onPress: () => router.push("/settings"),
          }}
        />
      </View>
    );
  const matchState = (match: TournamentMatch) =>
    match.is_bye
      ? { label: "부전승", tone: "neutral" as const }
      : match.status === "reported"
        ? { label: "결과 제출 완료", tone: "success" as const }
        : match.round_status === "finished"
          ? { label: "라운드 종료", tone: "neutral" as const }
          : { label: "결과 대기", tone: "accent" as const };
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{
        width: "100%",
        maxWidth: 760,
        alignSelf: "center",
        paddingBottom: 48,
      }}
      refreshControl={
        <RefreshControl
          refreshing={busy && !!data}
          onRefresh={refresh}
          tintColor={colors.accent}
          colors={[colors.accent]}
          progressBackgroundColor={colors.panel}
        />
      }
    >
      <Stack.Screen options={{ title: data?.name || t("내 경기") }} />
      {entrySheet}
      {report?.scope === scope && (
        <TournamentResult
          key={`${scope}:${report.match.id}`}
          match={report.match}
          onClose={() => setReport(null)}
          onSaved={refresh}
        />
      )}
      <Notice text={message || error} />
      {!data && busy && (
        <View style={{ gap: space.md }}>
          <Skeleton height={130} rounded={radius.lg} />
          <Skeleton height={170} rounded={radius.lg} />
        </View>
      )}
      {data && (
        <>
          <View style={matchStyles.hero}>
            <Badge
              label={tournamentStatus[data.status] || data.status}
              tone={statusTone(data.status)}
            />
            <Text style={type.title}>{data.name}</Text>
            <InfoLine
              icon="calendar-outline"
              text={new Date(data.event_date).toLocaleString(language)}
            />
            {!!data.venue && (
              <InfoLine icon="location-outline" text={data.venue} />
            )}
            <InfoLine icon="person-outline" text={data.participant_name} />
          </View>

          <Text style={matchStyles.heading}>{t("내 경기")}</Text>
          {!data.matches.length && (
            <EmptyState
              icon="hourglass-outline"
              title="아직 배정된 경기가 없습니다."
            />
          )}
          {data.matches.map((match) => {
            const state = matchState(match);
            return (
              <View key={match.id} style={matchStyles.match}>
                <View style={matchStyles.matchHead}>
                  <Text style={matchStyles.round}>
                    {"R" + match.round_number + " · " + match.table}
                  </Text>
                  <Badge label={state.label} tone={state.tone} />
                </View>
                <View style={matchStyles.score}>
                  <Text style={matchStyles.player} numberOfLines={2}>
                    {match.players.p1.name}
                  </Text>
                  <Text style={matchStyles.points}>
                    {match.score.p1 + " : " + match.score.p2}
                  </Text>
                  <Text
                    style={[matchStyles.player, { textAlign: "right" }]}
                    numberOfLines={2}
                  >
                    {match.players.p2?.name || "BYE"}
                  </Text>
                </View>
                <InfoLine
                  icon="time-outline"
                  text={
                    match.set_count +
                    " " +
                    t("세트") +
                    " · " +
                    t("라운드 종료 시각") +
                    " " +
                    new Date(match.round_ends_at).toLocaleTimeString(language)
                  }
                />
                {(match.can_open_calculator || match.can_report) && (
                  <View style={matchStyles.actions}>
                    {match.can_open_calculator && (
                      <Button
                        label="경기 계산기"
                        icon="calculator-outline"
                        variant="primary"
                        style={{ flex: 1 }}
                        loading={opening}
                        disabled={!online}
                        onPress={() => open(match)}
                      />
                    )}
                    {match.can_report && (
                      <Button
                        label="결과 제출"
                        icon="checkmark-done-outline"
                        style={{ flex: 1 }}
                        disabled={!online}
                        onPress={() => setReport({ scope, match })}
                      />
                    )}
                  </View>
                )}
              </View>
            );
          })}

          {!!data.decks.length && (
            <View style={{ marginTop: space.lg }}>
              <ListSection title="제출한 덱">
                {data.decks.map((d) => (
                  <ListRow
                    key={d.slot}
                    icon="layers-outline"
                    title={d.name}
                    subtitle={"#" + d.slot}
                    onPress={() =>
                      router.push({
                        pathname: "/deck/[id]",
                        params: {
                          id: String(d.id),
                          submission: String(d.submission_id),
                        },
                      })
                    }
                  />
                ))}
              </ListSection>
            </View>
          )}
          {!!data.description && (
            <>
              <Text style={matchStyles.heading}>{t("대회 안내")}</Text>
              <View style={styles.panel}>
                <Text selectable style={[styles.text, { lineHeight: 22 }]}>
                  {deckDescription(data.description)}
                </Text>
              </View>
            </>
          )}
        </>
      )}
    </ScrollView>
  );
}

const matchStyles = StyleSheet.create({
  hero: {
    gap: 6,
    padding: space.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  heading: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    marginTop: space.xl,
    marginBottom: space.sm,
    marginLeft: space.xs,
  },
  match: {
    gap: space.sm,
    padding: space.lg,
    marginBottom: space.md,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  matchHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  round: { color: colors.muted, fontSize: 14, fontWeight: "700" },
  score: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingVertical: space.sm,
  },
  player: { flex: 1, color: colors.text, fontSize: 16, fontWeight: "600" },
  points: {
    color: colors.accent,
    fontSize: 26,
    fontWeight: "800",
    fontVariant: ["tabular-nums"],
  },
  actions: { flexDirection: "row", gap: space.sm, marginTop: space.xs },
});
