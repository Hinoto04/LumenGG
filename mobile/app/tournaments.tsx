import React from "react";
import {
  View,
  Text,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
} from "react-native";
import { router } from "expo-router";
import { useApp } from "../src/provider";
import {
  useTournamentResource,
  tournamentStatus,
  type TournamentSummary,
} from "../src/tournaments";
import {
  Badge,
  EmptyState,
  Icon,
  Notice,
  Skeleton,
  colors,
  radius,
  space,
  styles,
} from "../src/ui";
import { InfoLine, statusTone } from "../src/tournament-ui";
import { cellStyle, listColumns, useScreen } from "../src/layout";

export default function Tournaments() {
  const { user, language } = useApp();
  // 가로 화면이나 넓은 화면에서는 목록을 여러 칸으로 놓는다.
  const { width } = useScreen();
  const listCols = listColumns(width);
  const { data, busy, message, refresh } = useTournamentResource<{
    tournaments: TournamentSummary[];
  }>("/tournaments");
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
  return (
    <View style={[styles.screen, { paddingBottom: 0 }]}>
      <Notice text={message} />
      <FlatList
        key={"columns-" + listCols}
        numColumns={listCols}
        columnWrapperStyle={listCols > 1 ? { gap: 12 } : undefined}
        data={data?.tournaments || []}
        keyExtractor={(d) => String(d.id)}
        contentContainerStyle={{ paddingBottom: 32 }}
        refreshControl={
          <RefreshControl
            refreshing={busy && !!data}
            onRefresh={refresh}
            tintColor={colors.accent}
            colors={[colors.accent]}
            progressBackgroundColor={colors.panel}
          />
        }
        ListEmptyComponent={
          busy ? (
            <View style={{ gap: space.md }}>
              {[0, 1].map((n) => (
                <Skeleton key={n} height={120} rounded={radius.lg} />
              ))}
            </View>
          ) : (
            <EmptyState
              icon="trophy-outline"
              title="참가한 대회가 없습니다."
              action={{ label: "새로고침", icon: "refresh", onPress: refresh }}
            />
          )
        }
        renderItem={({ item: d }) => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={d.name}
            onPress={() =>
              router.push({
                pathname: "/tournament/[id]",
                params: { id: String(d.id) },
              })
            }
            style={({ pressed }) => [
              listStyles.item,
              cellStyle(width, listCols),
              d.status === "running" && listStyles.running,
              pressed && { backgroundColor: colors.surface2 },
            ]}
          >
            <View style={listStyles.badges}>
              <Badge
                label={tournamentStatus[d.status] || d.status}
                tone={statusTone(d.status)}
              />
              {d.dropped && <Badge label="중도 탈락" tone="danger" />}
            </View>
            <Text style={listStyles.name} numberOfLines={2}>
              {d.name}
            </Text>
            <InfoLine
              icon="calendar-outline"
              text={new Date(d.event_date).toLocaleString(language)}
            />
            {!!d.venue && <InfoLine icon="location-outline" text={d.venue} />}
            <InfoLine icon="person-outline" text={d.participant_name} />
            <View style={listStyles.chevron}>
              <Icon name="chevron-forward" size={18} color={colors.subtle} />
            </View>
          </Pressable>
        )}
      />
    </View>
  );
}

const listStyles = StyleSheet.create({
  item: {
    padding: space.lg,
    paddingRight: 40,
    gap: 6,
    marginBottom: space.md,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  running: { borderColor: colors.accent },
  badges: { flexDirection: "row", gap: 6 },
  name: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 2,
  },
  chevron: {
    position: "absolute",
    right: space.md,
    top: 0,
    bottom: 0,
    justifyContent: "center",
  },
});
