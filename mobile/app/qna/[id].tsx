import React from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams, router, Stack } from "expo-router";
import { useApp } from "../../src/provider";
import { localized } from "../../src/core";
import {
  Badge,
  EmptyState,
  ListRow,
  ListSection,
  RichText,
  colors,
  radius,
  space,
  styles,
  type,
} from "../../src/ui";

export default function QnaDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { catalog, language } = useApp();
  const qna = catalog?.qna.find((q) => q.id === Number(id));
  if (!qna)
    return (
      <View style={styles.screen}>
        <EmptyState icon="search-outline" title="검색 결과가 없습니다." />
      </View>
    );
  const cards = qna.card_ids
    .map((cardId) => catalog?.cards.find((c) => c.id === cardId))
    .filter((card) => !!card);
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 48 }}
    >
      <Stack.Screen options={{ title: "Q&A #" + qna.id }} />
      <Text style={type.title}>{qna.title}</Text>
      <View style={detailStyles.meta}>
        {qna.faq && <Badge label="FAQ" tone="accent" />}
        {!!qna.tags && <Text style={styles.muted}>{qna.tags}</Text>}
      </View>
      <Block mark="Q" tone={colors.accent} soft={colors.accentSoft}>
        <RichText text={qna.question} />
      </Block>
      <Block mark="A" tone={colors.success} soft="rgba(127, 209, 166, 0.14)">
        <RichText text={qna.answer} />
      </Block>
      {cards.length > 0 && (
        <View style={{ marginTop: space.xl }}>
          <ListSection title="관련 카드">
            {cards.map((card) => (
              <ListRow
                key={card!.id}
                icon="albums-outline"
                title={localized(card!, language)}
                subtitle={card!.code || undefined}
                onPress={() =>
                  router.push({
                    pathname: "/card/[id]",
                    params: { id: card!.id },
                  })
                }
              />
            ))}
          </ListSection>
        </View>
      )}
    </ScrollView>
  );
}

function Block({
  mark,
  tone,
  soft,
  children,
}: {
  mark: string;
  tone: string;
  soft: string;
  children: React.ReactNode;
}) {
  return (
    <View style={[styles.panel, detailStyles.block]}>
      <View style={[detailStyles.mark, { backgroundColor: soft }]}>
        <Text style={[detailStyles.markText, { color: tone }]}>{mark}</Text>
      </View>
      <View style={{ flex: 1 }}>{children}</View>
    </View>
  );
}

const detailStyles = StyleSheet.create({
  meta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    flexWrap: "wrap",
    marginTop: space.sm,
    marginBottom: space.lg,
  },
  block: { flexDirection: "row", gap: space.md, alignItems: "flex-start" },
  mark: {
    width: 30,
    height: 30,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
  },
  markText: { fontWeight: "800", fontSize: 15 },
});
