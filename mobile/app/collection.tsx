import React, { useState } from "react";
import { View, Text, FlatList, Keyboard } from "react-native";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import { styles, Input, Button, CachedImage, Notice } from "../src/ui";
import { CollectionFilterScreen } from "../src/collection-filter-screen";
import {
  collectionRows,
  collectionFilterCount,
  emptyCollectionFilters,
  type CollectionFilters,
} from "../src/collection-data";
export default function Collection() {
  const { catalog, language, amounts, setAmount, status, t, syncErrors } =
    useApp();
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<CollectionFilters>({
    ...emptyCollectionFilters,
  });
  const [filterVisible, setFilterVisible] = useState(false);
  const rows = catalog
    ? collectionRows(catalog, filters, query, amounts, language)
    : [];
  return (
    <View style={styles.screen}>
      <Input value={query} onChangeText={setQuery} placeholder={t("검색")} />
      <View style={styles.row}>
        <Button
          label={`${t("필터")}${collectionFilterCount(filters) ? ` (${collectionFilterCount(filters)})` : ""}`}
          onPress={() => {
            Keyboard.dismiss();
            setFilterVisible(true);
          }}
        />
        <Text style={styles.muted}>
          {rows.length} {t("개")}
        </Text>
      </View>
      <CollectionFilterScreen
        visible={filterVisible}
        value={filters}
        query={query}
        onClose={() => setFilterVisible(false)}
        onApply={(next) => {
          setFilters(next);
          setFilterVisible(false);
        }}
      />
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
