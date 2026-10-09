import React, { useState } from "react";
import { View, Text, FlatList, Pressable } from "react-native";
import { router } from "expo-router";
import { useApp } from "../src/provider";
import { normalizeSearch } from "../src/core";
import { styles, Input, Button } from "../src/ui";
export default function Qna() {
  const { catalog, t } = useApp();
  const [query, setQuery] = useState(""),
    [faq, setFaq] = useState(false);
  const needle = normalizeSearch(query);
  const rows = (catalog?.qna || []).filter(
    (q) => (!needle || q.search?.includes(needle)) && (!faq || q.faq),
  );
  return (
    <View style={styles.screen}>
      <Input value={query} onChangeText={setQuery} placeholder={t("검색")} />
      <Button label={faq ? "FAQ ✓" : "FAQ"} onPress={() => setFaq(!faq)} />
      <FlatList
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        style={{ marginTop: 12 }}
        data={rows}
        keyExtractor={(q) => String(q.id)}
        renderItem={({ item: q }) => (
          <Pressable
            style={styles.panel}
            onPress={() =>
              router.push({ pathname: "/qna/[id]", params: { id: q.id } })
            }
          >
            <Text style={styles.text}>
              {q.faq ? "FAQ · " : ""}
              {q.title}
            </Text>
            <Text style={styles.muted}>{q.tags}</Text>
          </Pressable>
        )}
      />
    </View>
  );
}
