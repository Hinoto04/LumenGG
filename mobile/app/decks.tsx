import React from "react";
import { View, Text, FlatList, Alert } from "react-native";
import { router } from "expo-router";
import * as Crypto from "expo-crypto";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import { styles, Button, Notice } from "../src/ui";
export default function Decks() {
  const { decks, catalog, language, saveDeck, deleteDeck, status, t } =
    useApp();
  return (
    <View style={styles.screen}>
      <Button
        label="덱 작성"
        onPress={() =>
          router.push({ pathname: "/deck/[id]", params: { id: "new" } })
        }
      />
      <Notice text={status} />
      <FlatList
        data={decks.filter((d) => !d.deleted)}
        keyExtractor={(d) => d.uuid}
        renderItem={({ item: d }) => {
          const character = catalog?.characters.find(
            (c) => c.id === d.character_id,
          );
          return (
            <View style={styles.panel}>
              <Text style={styles.title}>{d.name || t("작성 중")}</Text>
              <Text style={styles.muted}>
                {character ? localized(character, language) : ""} ·{" "}
                {d.cards.reduce((s, c) => s + c.count, 0)} {t("장")} ·{" "}
                {t(d.visibility)}
              </Text>
              <Notice text={(d as any).sync_error || ""} />
              <View style={styles.row}>
                <Button
                  label="수정"
                  onPress={() =>
                    router.push({
                      pathname: "/deck/[id]",
                      params: { id: d.uuid },
                    })
                  }
                />
                <Button
                  label="복사"
                  onPress={async () => {
                    const copy = {
                      ...d,
                      uuid: Crypto.randomUUID(),
                      id: undefined,
                      name: d.name + " " + t("복사"),
                      locked: false,
                      visibility: "private" as const,
                    };
                    await saveDeck(copy);
                    router.push({
                      pathname: "/deck/[id]",
                      params: { id: copy.uuid },
                    });
                  }}
                />
                <Button
                  label="삭제"
                  danger
                  disabled={d.locked}
                  onPress={() =>
                    Alert.alert(t("삭제"), d.name, [
                      { text: t("취소") },
                      {
                        text: t("삭제"),
                        style: "destructive",
                        onPress: () => deleteDeck(d),
                      },
                    ])
                  }
                />
              </View>
            </View>
          );
        }}
      />
    </View>
  );
}
