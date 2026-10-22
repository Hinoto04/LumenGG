import React from "react";
import { View, Text, FlatList, Pressable } from "react-native";
import { router } from "expo-router";
import { useApp } from "../src/provider";
import {
  useTournamentResource,
  tournamentStatus,
  type TournamentSummary,
} from "../src/tournaments";
import { Button, Notice, colors, styles } from "../src/ui";

export default function Tournaments() {
  const { user, language, t } = useApp();
  const { data, busy, message, refresh } = useTournamentResource<{
    tournaments: TournamentSummary[];
  }>("/tournaments");
  return (
    <View style={styles.screen}>
      {!user ? (
        <View style={styles.panel}>
          <Notice text="참가한 대회를 확인하려면 로그인해주세요." />
          <Button label="로그인" onPress={() => router.push("/settings")} />
        </View>
      ) : (
        <>
          <View
            style={[
              styles.row,
              { justifyContent: "space-between", marginBottom: 12 },
            ]}
          >
            <Text style={styles.title}>{t("내 대회")}</Text>
            <Button label="새로고침" onPress={refresh} disabled={busy} />
          </View>
          <Notice text={message} />
          <FlatList
            data={data?.tournaments || []}
            keyExtractor={(d) => String(d.id)}
            ListEmptyComponent={
              <Notice text={busy ? "불러오는 중" : "참가한 대회가 없습니다."} />
            }
            renderItem={({ item: d }) => (
              <Pressable
                style={styles.panel}
                accessibilityRole="button"
                accessibilityLabel={d.name}
                onPress={() =>
                  router.push({
                    pathname: "/tournament/[id]",
                    params: { id: String(d.id) },
                  })
                }
              >
                <Text style={[styles.title, { fontSize: 19 }]}>{d.name}</Text>
                <Text
                  style={{
                    color:
                      d.status === "running" ? colors.accent : colors.muted,
                  }}
                >
                  {t(tournamentStatus[d.status] || d.status)}
                  {d.dropped ? ` · ${t("중도 탈락")}` : ""}
                </Text>
                <Text style={[styles.muted, { marginTop: 8 }]}>
                  {new Date(d.event_date).toLocaleString(language)}
                  {d.venue ? ` · ${d.venue}` : ""}
                </Text>
                <Text style={[styles.muted, { marginTop: 5 }]}>
                  {d.participant_name}
                </Text>
              </Pressable>
            )}
          />
        </>
      )}
    </View>
  );
}
