import React from "react";
import { ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useApp } from "../../src/provider";
import { localized } from "../../src/core";
import { styles, RichText, Button } from "../../src/ui";
export default function QnaDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { catalog, language, t } = useApp();
  const qna = catalog?.qna.find((q) => q.id === Number(id));
  if (!qna)
    return (
      <View style={styles.screen}>
        <Text style={styles.text}>{t("검색 결과가 없습니다.")}</Text>
      </View>
    );
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      <Text style={styles.title}>{qna.title}</Text>
      <View style={styles.panel}>
        <Text style={styles.text}>Q</Text>
        <RichText text={qna.question} />
      </View>
      <View style={styles.panel}>
        <Text style={styles.text}>A</Text>
        <RichText text={qna.answer} />
      </View>
      {qna.card_ids.map((id) => {
        const card = catalog?.cards.find((c) => c.id === id);
        return card ? (
          <View key={id} style={styles.panel}>
            <Button
              label={localized(card, language)}
              onPress={() =>
                router.push({ pathname: "/card/[id]", params: { id } })
              }
            />
          </View>
        ) : null;
      })}
    </ScrollView>
  );
}
