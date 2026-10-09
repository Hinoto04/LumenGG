import React, { useState } from "react";
import { View, Text, FlatList, ScrollView } from "react-native";
import { useApp } from "../src/provider";
import { localized, normalizeSearch } from "../src/core";
import { styles, Choices, Input, Button, CachedImage, Notice } from "../src/ui";
export default function Collection() {
  const { catalog, language, amounts, setAmount, status, t, syncErrors } =
    useApp();
  const [query, setQuery] = useState(""),
    [pack, setPack] = useState(""),
    [character, setCharacter] = useState(""),
    [rare, setRare] = useState(""),
    [type, setType] = useState(""),
    [onlyZero, setOnlyZero] = useState(false),
    [filters, setFilters] = useState(false);
  const needle = normalizeSearch(query);
  const rows = (catalog?.collection || []).filter(
    (c) =>
      (!needle || normalizeSearch(c.name + c.code).includes(needle)) &&
      (!pack || String(c.pack_id) === pack) &&
      (!character || String(c.character_id) === character) &&
      (!rare || c.rare === rare) &&
      (!type || c.item_type === type) &&
      (!onlyZero || !amounts[c.id]),
  );
  return (
    <View style={styles.screen}>
      <Input value={query} onChangeText={setQuery} placeholder={t("검색")} />
      <View style={styles.row}>
        <Button label="필터" onPress={() => setFilters(!filters)} />
        <Button
          label={onlyZero ? "미보유 ✓" : "미보유"}
          onPress={() => setOnlyZero(!onlyZero)}
        />
      </View>
      {filters && (
        <ScrollView
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          style={{ maxHeight: 230, marginTop: 10 }}
        >
          <Choices
            value={pack}
            onChange={setPack}
            values={[
              { key: "", label: t("전체 팩") },
              ...(catalog?.packs || []).map((p) => ({
                key: String(p.id),
                label: localized(p, language),
              })),
            ]}
          />
          <Choices
            value={character}
            onChange={setCharacter}
            values={[
              { key: "", label: t("전체") },
              ...(catalog?.characters || []).map((c) => ({
                key: String(c.id),
                label: localized(c, language),
              })),
            ]}
          />
          <Choices
            value={rare}
            onChange={setRare}
            values={[
              { key: "", label: t("전체 레어도") },
              ...[...new Set(catalog?.collection.map((c) => c.rare))].map(
                (v) => ({ key: v, label: v }),
              ),
            ]}
          />
          <Choices
            value={type}
            onChange={setType}
            values={[
              { key: "", label: t("전체 종류") },
              ...["card", "skin", "token", "other"].map((v) => ({
                key: v,
                label: t(v),
              })),
            ]}
          />
        </ScrollView>
      )}
      <Notice text={status} />
      <FlatList
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        data={rows}
        keyExtractor={(c) => String(c.id)}
        renderItem={({ item: c }) => {
          const card = catalog?.cards.find((card) => card.id === c.card_id);
          const amount = amounts[c.id] || 0;
          return (
            <View style={styles.panel}>
              <View style={styles.row}>
                <CachedImage url={c.img_sm || c.image} />
                <View style={{ flex: 1 }}>
                  <Text style={styles.text}>
                    {card ? localized(card, language) : c.name}
                  </Text>
                  <Text style={styles.muted}>
                    {c.code} · {c.rare}
                  </Text>
                  <Notice text={syncErrors[c.id] || ""} />
                  <View style={styles.row}>
                    <Button
                      label="−"
                      disabled={!amount}
                      onPress={() => setAmount(c.id, (current) => current - 1)}
                    />
                    <Text style={styles.text}>{amount}</Text>
                    <Button
                      label="+"
                      onPress={() => setAmount(c.id, (current) => current + 1)}
                    />
                  </View>
                </View>
              </View>
            </View>
          );
        }}
      />
    </View>
  );
}
