import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import { FilterChoices, FilterSheet, filterStyles } from "./filter-sheet";
import { useApp } from "./provider";
import { localized, normalizeSearch } from "./core";
import {
  emptyCardFilters,
  filterError,
  matchesCardFilters,
  type CardFilters,
} from "./card-filters";
import { colors, Input } from "./ui";

export function CardFilterScreen({
  visible,
  value,
  query,
  onApply,
  onClose,
}: {
  visible: boolean;
  value: CardFilters;
  query: string;
  onApply: (value: CardFilters) => void;
  onClose: () => void;
}) {
  const { catalog, language, t } = useApp();
  const [draft, setDraft] = useState<CardFilters>({ ...value });
  useEffect(() => {
    if (visible) setDraft({ ...value });
  }, [visible, value]);
  const error = filterError(draft);
  const needle = normalizeSearch(query);
  const count = (catalog?.cards || []).filter(
    (card) =>
      (!needle || card.search?.includes(needle)) &&
      matchesCardFilters(card, draft),
  ).length;
  function set(key: keyof CardFilters, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  function choices(
    title: string,
    key: "character" | "type" | "pos",
    values: { key: string; label: string }[],
  ) {
    return (
      <FilterChoices
        title={title}
        value={draft[key]}
        values={values}
        onChange={(value) => set(key, value)}
      />
    );
  }
  function range(
    title: string,
    min: "frameMin" | "damageMin",
    max: "frameMax" | "damageMax",
  ) {
    return (
      <View style={filterStyles.section}>
        <Text style={filterStyles.heading}>{t(title)}</Text>
        <View style={filterStyles.range}>
          <Input
            accessibilityLabel={`${t(title)} ${t("최소값")}`}
            placeholder={t("최소값")}
            value={draft[min]}
            onChangeText={(v) => set(min, v.trim())}
            keyboardType="numeric"
            style={filterStyles.input}
          />
          <Text style={{ color: colors.muted }}>—</Text>
          <Input
            accessibilityLabel={`${t(title)} ${t("최대값")}`}
            placeholder={t("최대값")}
            value={draft[max]}
            onChangeText={(v) => set(max, v.trim())}
            keyboardType="numeric"
            style={filterStyles.input}
          />
        </View>
      </View>
    );
  }
  return (
    <FilterSheet
      visible={visible}
      title="카드 필터"
      count={count}
      error={error}
      onClose={onClose}
      onReset={() => setDraft({ ...emptyCardFilters })}
      onApply={() => onApply({ ...draft })}
    >
      {choices("캐릭터", "character", [
        { key: "", label: t("전체") },
        ...(catalog?.characters || []).map((c) => ({
          key: String(c.id),
          label: localized(c, language),
        })),
      ])}
      {choices("카드 종류", "type", [
        { key: "", label: t("전체") },
        ...[...new Set(catalog?.cards.map((c) => c.type) || [])]
          .filter(Boolean)
          .map((type) => ({ key: type, label: t(type) })),
      ])}
      {choices("공격 판정", "pos", [
        { key: "", label: t("전체") },
        ...["상단", "중단", "하단"].map((pos) => ({
          key: pos,
          label: t(pos),
        })),
      ])}
      {range("속도", "frameMin", "frameMax")}
      {range("대미지", "damageMin", "damageMax")}
    </FilterSheet>
  );
}
