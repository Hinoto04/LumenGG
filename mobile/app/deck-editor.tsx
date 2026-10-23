import React, { useEffect, useState } from "react";
import { ScrollView, View, Text } from "react-native";
import { router, useLocalSearchParams, useFocusEffect } from "expo-router";
import * as Crypto from "expo-crypto";
import { useApp } from "../src/provider";
import { localized } from "../src/core";
import { deckIssues, isTrait } from "../src/deck-rules";
import { importDeckCode } from "../src/deck-exchange";
import { request } from "../src/api";
import { preference, setPreference } from "../src/storage";
import { userMessage } from "../src/errors";
import type { Deck, RegulationVersion } from "../src/types";
import { styles, Input, Button, Choices, Notice } from "../src/ui";

export default function DeckEditor() {
  const params = useLocalSearchParams<{ id?: string; copy?: string }>();
  const { catalog, decks, language, user, scope, saveDeck } = useApp();
  const [loadedScope, setLoadedScope] = useState(scope);
  const [deck, setDeck] = useState<Deck | null>(null),
    [query, setQuery] = useState(""),
    [zone, setZone] = useState("cards"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [importText, setImportText] = useState(""),
    [versions, setVersions] = useState<RegulationVersion[]>([]);
  useEffect(() => {
    if (!catalog) return;
    let live = true;
    setDeck(null);
    setError("");
    (async () => {
      const id = params.id || params.copy;
      const source = id
        ? decks.find((d) => d.uuid === id || String(d.id) === id) ||
          (await request(
            id.startsWith("submission:")
              ? `/submitted-decks/${id.split(":")[1]}`
              : `/decks/${id}`,
            {},
            !!user,
          ))
        : null;
      if (!live) return;
      const initial: Deck = source
        ? { ...source }
        : {
            uuid: Crypto.randomUUID(),
            name: "새 덱",
            character_id:
              catalog.characters.find((c) => c.traits?.length)?.id ||
              catalog.characters[0]?.id ||
              1,
            description: "",
            keyword: "",
            tags: "",
            visibility: "private",
            cards: [],
            reserve_cards: [],
          };
      if (params.copy) {
        delete initial.id;
        initial.uuid = Crypto.randomUUID();
        initial.locked = false;
        initial.author = user || undefined;
        initial.name += " 복사본";
      }
      if (initial.locked)
        throw new Error("대회 제출 덱은 복사한 뒤 편집해주세요.");
      initial.schema_version = 2;
      initial.reserve_cards ||= [];
      const traits = catalog.characters.find(
        (c) => c.id === initial.character_id,
      )?.traits;
      if (!initial.trait_card_id && traits?.length === 1)
        initial.trait_card_id = traits[0]!.id;
      setDeck(initial);
      setLoadedScope(scope);
      const cached = await preference<RegulationVersion[]>(
        `regulations:${scope}`,
        catalog.rules.regulations || [],
      );
      if (live)
        setVersions(
          initial.regulation &&
            !cached.some((v) => v.id === initial.regulation!.id)
            ? [...cached, initial.regulation]
            : cached,
        );
      try {
        const response = await request("/regulations", {}, !!user);
        if (live)
          setVersions(
            initial.regulation &&
              !response.versions.some(
                (v: any) => v.id === initial.regulation!.id,
              )
              ? [...response.versions, initial.regulation]
              : response.versions,
          );
        await setPreference(`regulations:${scope}`, response.versions);
      } catch {}
    })().catch((e) => live && setError(userMessage(e)));
    return () => {
      live = false;
    };
  }, [catalog, params.id, params.copy, scope]);
  useFocusEffect(
    React.useCallback(() => {
      let live = true;
      request("/regulations", {}, !!user)
        .then((result) => {
          if (live)
            setVersions((previous) => [
              ...result.versions,
              ...previous.filter(
                (v) => !result.versions.some((r: any) => r.id === v.id),
              ),
            ]);
          return setPreference(`regulations:${scope}`, result.versions);
        })
        .catch(() => {});
      return () => {
        live = false;
      };
    }, [scope, user?.id]),
  );
  if (!catalog || !deck || loadedScope !== scope)
    return (
      <View style={styles.screen}>
        <Notice text={error || "불러오는 중"} />
      </View>
    );
  const issues = deckIssues(deck, catalog, "draft"),
    character = catalog.characters.find((c) => c.id === deck.character_id);
  const change = (patch: Partial<Deck>) => setDeck({ ...deck, ...patch });
  const setCount = (
    id: number,
    field: "count" | "hand" | "side",
    value: number,
  ) => {
    const rows = deck.cards.map((e) => ({ ...e })),
      row = rows.find((e) => e.card_id === id);
    if (!row) return;
    row[field] = value;
    const card = catalog.cards.find((c) => c.id === id)!;
    if (card.ultimate) {
      row.hand = 0;
      row.side = 0;
    } else if (card.type.includes("특수")) {
      row.hand = 0;
      row.side = row.count;
    }
    change({ cards: rows.filter((e) => e.count > 0) });
  };
  const add = (id: number) => {
    if (zone === "reserve") {
      const rows = (deck.reserve_cards || []).map((e) => ({ ...e })),
        row = rows.find((e) => e.card_id === id);
      if (row) row.count++;
      else rows.push({ card_id: id, count: 1 });
      change({ reserve_cards: rows });
    } else {
      const rows = deck.cards.map((e) => ({ ...e })),
        row = rows.find((e) => e.card_id === id),
        card = catalog.cards.find((c) => c.id === id)!;
      if (row) {
        row.count++;
        if (!card.ultimate && card.type.includes("특수")) row.side++;
      } else
        rows.push({
          card_id: id,
          count: 1,
          hand: 0,
          side: !card.ultimate && card.type.includes("특수") ? 1 : 0,
        });
      change({ cards: rows });
    }
  };
  const filtered = catalog.cards
    .filter(
      (c) =>
        c.type !== "토큰" &&
        (zone === "reserve" || !isTrait(c)) &&
        `${localized(c, language)} ${c.code}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .slice(0, 60);
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 50 }}
    >
      <Text style={styles.title}>덱 작성</Text>
      <Input
        accessibilityLabel="가져올 덱 코드"
        placeholder="가져올 덱 코드 붙여넣기"
        value={importText}
        onChangeText={setImportText}
      />
      <Button
        label="덱 코드로 가져오기"
        disabled={!importText}
        onPress={() => {
          try {
            const imported = importDeckCode(
              importText,
              catalog,
              Crypto.randomUUID(),
            );
            setDeck(imported);
            if (imported.regulation)
              setVersions((previous) => [
                ...previous.filter((v) => v.id !== imported.regulation!.id),
                imported.regulation!,
              ]);
            setImportText("");
          } catch (e) {
            setError(userMessage(e));
          }
        }}
      />
      <Notice text={error} />
      {catalog.schema_version !== 2 && (
        <Notice text="특성·규정 데이터를 업데이트한 뒤 새 형식으로 저장해주세요." />
      )}
      <Input
        accessibilityLabel="덱 이름"
        value={deck.name}
        onChangeText={(name) => change({ name })}
      />
      <Text style={styles.text}>캐릭터</Text>
      <Choices
        value={String(deck.character_id)}
        onChange={(id) =>
          change({
            character_id: Number(id),
            trait_card_id:
              catalog.characters.find((c) => c.id === Number(id))?.traits
                ?.length === 1
                ? catalog.characters.find((c) => c.id === Number(id))!
                    .traits![0]!.id
                : null,
          })
        }
        values={catalog.characters.map((c) => ({
          key: String(c.id),
          label: localized(c, language),
        }))}
      />
      <Text style={styles.text}>특성</Text>
      <Choices
        value={String(deck.trait_card_id || "")}
        onChange={(id) => change({ trait_card_id: Number(id) })}
        values={(character?.traits || []).map((t) => ({
          key: String(t.id),
          label: localized(t, language) || t.name,
        }))}
      />
      <Button
        label="규정 작성·복사"
        onPress={() => router.push("/regulations")}
      />
      <Text style={styles.text}>적용 규정</Text>
      <Choices
        value={String(deck.regulation_version_id || "")}
        onChange={(id) =>
          change({
            regulation_version_id: Number(id) || null,
            regulation_rules: versions.find((v) => v.id === Number(id))?.rules,
          })
        }
        values={[
          { key: "", label: "기본 규정" },
          ...versions.map((v) => ({
            key: String(v.id),
            label: `${v.name} / ${v.version}`,
          })),
        ]}
      />
      <Choices
        value={deck.visibility}
        onChange={(v) => change({ visibility: v as Deck["visibility"] })}
        values={[
          { key: "private", label: "비공개" },
          { key: "unlisted", label: "일부 공개" },
          { key: "public", label: "공개" },
        ]}
      />
      <Input
        accessibilityLabel="덱 설명"
        placeholder="덱 설명"
        multiline
        value={deck.description}
        onChangeText={(description) => change({ description })}
      />
      <Text style={styles.title}>기술 구성 · 시작 배치</Text>
      {deck.cards.map((e) => (
        <View key={e.card_id} style={styles.panel}>
          <Text style={styles.text}>
            {localized(
              catalog.cards.find((c) => c.id === e.card_id) || {
                localized: {},
              },
              language,
            )}
          </Text>
          <View style={styles.row}>
            {(["count", "hand", "side"] as const).map((field) => (
              <View key={field}>
                <Text style={styles.muted}>
                  {field === "count"
                    ? "매수"
                    : field === "hand"
                      ? "시작 패"
                      : "사이드"}
                </Text>
                <Input
                  accessibilityLabel={`${e.card_id} ${field}`}
                  keyboardType="number-pad"
                  style={{ width: 72 }}
                  value={String(e[field])}
                  onChangeText={(v) => setCount(e.card_id, field, Number(v))}
                />
              </View>
            ))}
          </View>
        </View>
      ))}
      <Text style={styles.title}>
        교체 덱 · {(deck.reserve_cards || []).reduce((n, e) => n + e.count, 0)}
        장
      </Text>
      {(deck.reserve_cards || []).map((e) => (
        <View key={e.card_id} style={styles.row}>
          <Text style={styles.text}>
            {localized(
              catalog.cards.find((c) => c.id === e.card_id) || {
                localized: {},
              },
              language,
            )}{" "}
            × {e.count}
          </Text>
          <Button
            label="1장 빼기"
            onPress={() =>
              change({
                reserve_cards: (deck.reserve_cards || [])
                  .map((r) =>
                    r.card_id === e.card_id ? { ...r, count: r.count - 1 } : r,
                  )
                  .filter((r) => r.count > 0),
              })
            }
          />
        </View>
      ))}
      <Choices
        value={zone}
        onChange={setZone}
        values={[
          { key: "cards", label: "기본 구성에 추가" },
          { key: "reserve", label: "교체 덱에 추가" },
        ]}
      />
      <Input
        accessibilityLabel="추가할 카드 검색"
        placeholder="카드명·번호 검색"
        value={query}
        onChangeText={setQuery}
      />
      {filtered.map((c) => (
        <View key={c.id} style={styles.row}>
          <Text style={[styles.text, { flex: 1 }]}>
            {localized(c, language)} · {c.code}
          </Text>
          <Button label="추가" onPress={() => add(c.id)} />
        </View>
      ))}
      <Text style={styles.title}>편성 확인</Text>
      {issues.map((i, n) => (
        <Notice key={n} text={i.message} />
      ))}
      <Button
        label="초안 저장"
        disabled={
          busy ||
          catalog.schema_version !== 2 ||
          issues.some((i) => i.severity === "error") ||
          !deck.name.trim()
        }
        onPress={async () => {
          setBusy(true);
          try {
            await saveDeck(deck);
            router.replace({
              pathname: "/deck/[id]",
              params: { id: deck.uuid },
            });
          } catch (e) {
            setError(userMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      />
    </ScrollView>
  );
}
