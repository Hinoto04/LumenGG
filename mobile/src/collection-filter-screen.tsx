import React, { useEffect, useState } from "react";
import { useApp } from "./provider";
import { localized } from "./core";
import {
  collectionRows,
  emptyCollectionFilters,
  type CollectionFilters,
} from "./collection-data";
import { FilterChoices, FilterSheet } from "./filter-sheet";

export function CollectionFilterScreen({
  visible,
  value,
  query,
  onApply,
  onClose,
}: {
  visible: boolean;
  value: CollectionFilters;
  query: string;
  onApply: (filters: CollectionFilters) => void;
  onClose: () => void;
}) {
  const { catalog, language, amounts, t } = useApp();
  const [draft, setDraft] = useState({ ...value });
  useEffect(() => {
    if (visible) setDraft({ ...value });
  }, [visible, value]);
  const count = catalog
    ? collectionRows(catalog, draft, query, amounts, language).length
    : 0;
  const set = (key: keyof CollectionFilters, value: string | boolean) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const all = { key: "", label: t("전체") };
  return (
    <FilterSheet
      visible={visible}
      title="컬렉션 필터"
      unit="개"
      count={count}
      onClose={onClose}
      onReset={() => setDraft({ ...emptyCollectionFilters })}
      onApply={() => onApply({ ...draft })}
    >
      <FilterChoices
        title="팩"
        value={draft.pack}
        onChange={(value) => set("pack", value)}
        values={[
          all,
          ...(catalog?.packs || []).map((pack) => ({
            key: String(pack.id),
            label: localized(pack, language),
          })),
        ]}
      />
      <FilterChoices
        title="캐릭터"
        value={draft.character}
        onChange={(value) => set("character", value)}
        values={[
          all,
          ...(catalog?.characters || []).map((character) => ({
            key: String(character.id),
            label: localized(character, language),
          })),
        ]}
      />
      <FilterChoices
        title="레어도"
        value={draft.rare}
        onChange={(value) => set("rare", value)}
        values={[
          all,
          ...[...new Set(catalog?.collection.map((item) => item.rare) || [])]
            .filter(Boolean)
            .map((rare) => ({ key: rare, label: rare })),
        ]}
      />
      <FilterChoices
        title="종류"
        value={draft.type}
        onChange={(value) => set("type", value)}
        values={[
          all,
          ...["card", "skin", "token", "other"].map((type) => ({
            key: type,
            label: t(type),
          })),
        ]}
      />
      <FilterChoices
        title="보유 상태"
        value={draft.onlyZero ? "zero" : ""}
        onChange={(value) => set("onlyZero", value === "zero")}
        values={[all, { key: "zero", label: t("미보유") }]}
      />
    </FilterSheet>
  );
}
