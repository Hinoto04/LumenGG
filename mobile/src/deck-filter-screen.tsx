import React, { useEffect, useState } from "react";
import { useApp } from "./provider";
import { localized } from "./core";
import { bookmarkedDecks, matchingDecks, publicDeckPath } from "./deck-display";
import { request } from "./api";
import { userMessage } from "./errors";
import { Notice } from "./ui";
import { FilterChoices, FilterCharacters, FilterSheet } from "./filter-sheet";

export interface DeckFilters {
  mode: "mine" | "public";
  character: string;
  trait?: string;
  regulation?: string;
  /** 북마크한 덱만 본다. 로그인했을 때만 쓴다. */
  bookmarked?: boolean;
}
export const defaultDeckFilters: DeckFilters = {
  mode: "mine",
  character: "",
  trait: "",
  regulation: "",
  bookmarked: false,
};

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
  const { catalog, language, decks, user, scope, bookmarks, t } = useApp();
  const [draft, setDraft] = useState<DeckFilters>({ ...value });
  const [preview, setPreview] = useState<{ key: string; count: number } | null>(
    null,
  );
  const [message, setMessage] = useState("");
  const onlyBookmarked = !!user && !!draft.bookmarked;
  const key = `${scope}:${query.trim()}:${draft.character}:${draft.trait || ""}:${draft.regulation || ""}:${onlyBookmarked}`;
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
          publicDeckPath({
            query,
            character: draft.character,
            trait: draft.trait,
            regulation: draft.regulation,
            bookmarked: onlyBookmarked,
          }),
          {},
          !!user,
          false,
          user?.id,
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
      ? bookmarkedDecks(
          matchingDecks(
            decks,
            query,
            draft.character,
            draft.trait,
            draft.regulation,
          ),
          bookmarks,
          onlyBookmarked,
        ).length
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
      {!!user && (
        <FilterChoices
          title="북마크"
          value={draft.bookmarked ? "bookmarked" : ""}
          onChange={(next) =>
            setDraft((d) => ({ ...d, bookmarked: next === "bookmarked" }))
          }
          values={[
            { key: "", label: t("전체") },
            { key: "bookmarked", label: t("북마크한 덱만") },
          ]}
        />
      )}
      <FilterCharacters
        value={draft.character}
        characters={catalog?.characters || []}
        onChange={(character) =>
          // 캐릭터를 바꾸면 다른 캐릭터의 특성 조건은 의미가 없으므로 지운다.
          setDraft((d) => ({ ...d, character, trait: "" }))
        }
      />
      <FilterChoices
        title="특성"
        value={draft.trait || ""}
        onChange={(trait) => setDraft((d) => ({ ...d, trait }))}
        values={[
          { key: "", label: t("전체") },
          ...(
            catalog?.characters
              .filter(
                (c) => !draft.character || String(c.id) === draft.character,
              )
              .flatMap((c) => c.traits || []) || []
          ).map((trait) => ({
            key: String(trait.id),
            label: localized(trait, language) || trait.name,
          })),
        ]}
      />
      <FilterChoices
        title="규정"
        value={draft.regulation || ""}
        onChange={(regulation) => setDraft((d) => ({ ...d, regulation }))}
        values={[
          { key: "", label: t("전체") },
          ...(catalog?.rules.regulations || []).map((v) => ({
            key: String(v.id),
            label: `${v.name} / ${v.version}`,
          })),
        ]}
      />
      <Notice text={message} />
    </FilterSheet>
  );
}
