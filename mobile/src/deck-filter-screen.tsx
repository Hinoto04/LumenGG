import React, { useEffect, useState } from "react";
import { useApp } from "./provider";
import { localized } from "./core";
import { matchingDecks } from "./deck-display";
import { request } from "./api";
import { userMessage } from "./errors";
import { Notice } from "./ui";
import { FilterChoices, FilterSheet } from "./filter-sheet";

export interface DeckFilters {
  mode: "mine" | "public";
  character: string;
}
export const defaultDeckFilters: DeckFilters = { mode: "mine", character: "" };

export function DeckFilterScreen({
  visible,
  value,
  query,
  onApply,
  onClose,
}: {
  visible: boolean;
  value: DeckFilters;
  query: string;
  onApply: (filters: DeckFilters) => void;
  onClose: () => void;
}) {
  const { catalog, language, decks, user, scope, t } = useApp();
  const [draft, setDraft] = useState<DeckFilters>({ ...value });
  const [preview, setPreview] = useState<{ key: string; count: number } | null>(
    null,
  );
  const [message, setMessage] = useState("");
  const key = `${scope}:${query.trim()}:${draft.character}`;
  useEffect(() => {
    if (visible) setDraft({ ...value });
  }, [visible, value]);
  useEffect(() => {
    setPreview(null);
    setMessage("");
    if (!visible || draft.mode !== "public") return;
    let live = true;
    const timer = setTimeout(async () => {
      try {
        const result = await request(
          `/decks?scope=public&q=${encodeURIComponent(query.trim())}&character_id=${draft.character}`,
          {},
          false,
        );
        if (live) setPreview({ key, count: result.count });
      } catch (err) {
        if (live) setMessage(userMessage(err));
      }
    }, 350);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [visible, draft.mode, key]);
  const count =
    draft.mode === "mine"
      ? user
        ? matchingDecks(decks, query, draft.character).length
        : 0
      : preview?.key === key
        ? preview.count
        : null;
  return (
    <FilterSheet
      visible={visible}
      title="덱 필터"
      count={count}
      unit="덱"
      onClose={onClose}
      onReset={() => setDraft({ ...defaultDeckFilters })}
      onApply={() => onApply({ ...draft })}
    >
      <FilterChoices
        title="덱 목록"
        value={draft.mode}
        onChange={(mode) =>
          setDraft((d) => ({ ...d, mode: mode as DeckFilters["mode"] }))
        }
        values={[
          { key: "mine", label: t("내 덱") },
          { key: "public", label: t("공개 덱") },
        ]}
      />
      <FilterChoices
        title="캐릭터"
        value={draft.character}
        onChange={(character) => setDraft((d) => ({ ...d, character }))}
        values={[
          { key: "", label: t("전체") },
          ...(catalog?.characters || []).map((c) => ({
            key: String(c.id),
            label: localized(c, language),
          })),
        ]}
      />
      <Notice
        text={
          draft.mode === "mine" && !user
            ? "내 덱을 확인하려면 로그인해주세요."
            : message
        }
      />
    </FilterSheet>
  );
}
