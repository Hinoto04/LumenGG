import React, { useEffect, useState } from "react";
import { ScrollView, StyleSheet, View, Text } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
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
import {
  Badge,
  Button,
  Chip,
  EmptyState,
  Icon,
  IconButton,
  Input,
  Notice,
  SearchInput,
  Segmented,
  Skeleton,
  Stepper,
  colors,
  radius,
  space,
  styles,
} from "../src/ui";

const NEUTRAL_CHARACTER_ID = 1;
const KIMERA_CHARACTER_ID = 15;

export default function DeckEditor() {
  const params = useLocalSearchParams<{ id?: string; copy?: string }>();
  const { catalog, decks, language, user, scope, saveDeck, t } = useApp();
  const insets = useSafeAreaInsets();
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
        {error ? (
          <EmptyState icon="alert-circle-outline" title={error} />
        ) : (
          <View style={{ gap: space.md }}>
            <Skeleton height={48} />
            <Skeleton height={180} rounded={radius.lg} />
            <Skeleton height={120} rounded={radius.lg} />
          </View>
        )}
      </View>
    );
  const issues = deckIssues(deck, catalog, "draft"),
    character = catalog.characters.find((c) => c.id === deck.character_id);
  const change = (patch: Partial<Deck>) => setDeck({ ...deck, ...patch });
  const keepsCardForCharacter = (cardId: number, characterId: number) => {
    const card = catalog.cards.find((c) => c.id === cardId);
    if (!card) return false;
    if (card.character_id === NEUTRAL_CHARACTER_ID) return true;
    if (card.character_id === characterId) return true;
    // 키메라는 다른 캐릭터의 공격 기술을 덱에 넣을 수 있다.
    return (
      characterId === KIMERA_CHARACTER_ID &&
      !card.ultimate &&
      !isTrait(card) &&
      card.type.includes("공격")
    );
  };
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
  const cardOf = (id: number) => catalog.cards.find((c) => c.id === id);
  const nameOf = (id: number) => {
    const card = cardOf(id);
    return card ? localized(card, language) : "#" + id;
  };
  const setReserve = (id: number, count: number) =>
    change({
      reserve_cards: (deck.reserve_cards || [])
        .map((r) => (r.card_id === id ? { ...r, count } : r))
        .filter((r) => r.count > 0),
    });
  const total = deck.cards.reduce((n, e) => n + e.count, 0);
  const reserveTotal = (deck.reserve_cards || []).reduce(
    (n, e) => n + e.count,
    0,
  );
  const errors = issues.filter((i) => i.severity === "error");
  const blocked =
    busy ||
    catalog.schema_version !== 2 ||
    errors.length > 0 ||
    !deck.name.trim();
  const inDeck = (id: number) =>
    zone === "reserve"
      ? (deck.reserve_cards || []).find((e) => e.card_id === id)?.count || 0
      : deck.cards.find((e) => e.card_id === id)?.count || 0;
  const save = async () => {
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
  };
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        style={{ flex: 1 }}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{
          padding: space.lg,
          paddingBottom: 120 + insets.bottom,
        }}
      >
        <Notice text={error} />
        {catalog.schema_version !== 2 && (
          <Notice text="특성·규정 데이터를 업데이트한 뒤 새 형식으로 저장해주세요." />
        )}

        <EditorSection title="기본 정보">
          <FieldLabel text="덱 이름" />
          <Input
            accessibilityLabel={t("덱 이름")}
            value={deck.name}
            onChangeText={(name) => change({ name })}
          />
          <FieldLabel text="캐릭터" />
          <ChipRow>
            {catalog.characters.map((c) => (
              <Chip
                key={c.id}
                label={localized(c, language)}
                selected={deck.character_id === c.id}
                onPress={() =>
                  change({
                    character_id: c.id,
                    // 캐릭터를 바꾸면 새 캐릭터가 쓸 수 없는 카드만 정리하고
                    // 세츠메이(중립) 카드는 남긴다.
                    cards: deck.cards.filter((e) =>
                      keepsCardForCharacter(e.card_id, c.id),
                    ),
                    reserve_cards: (deck.reserve_cards || []).filter((e) =>
                      keepsCardForCharacter(e.card_id, c.id),
                    ),
                    trait_card_id:
                      c.traits?.length === 1 ? c.traits[0]!.id : null,
                  })
                }
              />
            ))}
          </ChipRow>
          {!!character?.traits?.length && (
            <>
              <FieldLabel text="특성" />
              <ChipRow>
                {character.traits.map((trait) => (
                  <Chip
                    key={trait.id}
                    label={localized(trait, language) || trait.name}
                    selected={deck.trait_card_id === trait.id}
                    onPress={() => change({ trait_card_id: trait.id })}
                  />
                ))}
              </ChipRow>
            </>
          )}
          <FieldLabel text="공개 범위" />
          <Segmented
            value={deck.visibility}
            onChange={(v) => change({ visibility: v as Deck["visibility"] })}
            values={[
              { key: "private", label: "비공개", icon: "lock-closed-outline" },
              { key: "unlisted", label: "일부 공개", icon: "link-outline" },
              { key: "public", label: "공개", icon: "globe-outline" },
            ]}
          />
          <View style={editorStyles.labelRow}>
            <FieldLabel text="적용 규정" />
            <Button
              label="규정 작성·복사"
              icon="document-text-outline"
              variant="ghost"
              size="sm"
              onPress={() => router.push("/regulations")}
            />
          </View>
          <ChipRow>
            <Chip
              label="기본 규정"
              selected={!deck.regulation_version_id}
              onPress={() =>
                change({
                  regulation_version_id: null,
                  regulation_rules: undefined,
                })
              }
            />
            {versions.map((v) => (
              <Chip
                key={v.id}
                label={v.name + " / " + v.version}
                selected={deck.regulation_version_id === v.id}
                onPress={() =>
                  change({
                    regulation_version_id: v.id,
                    regulation_rules: v.rules,
                  })
                }
              />
            ))}
          </ChipRow>
          <FieldLabel text="덱 설명" />
          <Input
            accessibilityLabel={t("덱 설명")}
            placeholder={t("덱 설명")}
            multiline
            textAlignVertical="top"
            style={{ minHeight: 96 }}
            value={deck.description}
            onChangeText={(description) => change({ description })}
          />
        </EditorSection>

        <EditorSection title="기술 구성 · 시작 배치" count={total}>
          {deck.cards.length === 0 && (
            <Text style={styles.muted}>
              {t("아직 카드가 없습니다. 아래 카드 추가에서 넣어 주세요.")}
            </Text>
          )}
          {deck.cards.map((e, index) => {
            const card = cardOf(e.card_id);
            const special =
              !!card && !card.ultimate && card.type.includes("특수");
            return (
              <View
                key={e.card_id}
                style={[
                  editorStyles.cardRow,
                  index > 0 && editorStyles.divider,
                ]}
              >
                <View style={editorStyles.cardHead}>
                  <Text style={editorStyles.cardName} numberOfLines={1}>
                    {nameOf(e.card_id)}
                  </Text>
                  {card?.ultimate && <Badge label="얼티밋" tone="danger" />}
                  {special && <Badge label="특수" tone="accent" />}
                </View>
                <View style={editorStyles.steppers}>
                  {(["count", "hand", "side"] as const).map((field) => {
                    const locked =
                      field !== "count" && (!!card?.ultimate || special);
                    const label =
                      field === "count"
                        ? "매수"
                        : field === "hand"
                          ? "시작 패"
                          : "사이드";
                    return (
                      <View key={field} style={editorStyles.stepperCell}>
                        <Text style={editorStyles.stepperLabel}>
                          {t(label)}
                        </Text>
                        <Stepper
                          label={nameOf(e.card_id) + " " + t(label)}
                          value={e[field]}
                          disabled={locked}
                          onChange={(v) => setCount(e.card_id, field, v)}
                        />
                      </View>
                    );
                  })}
                </View>
              </View>
            );
          })}
        </EditorSection>

        <EditorSection title="교체 덱" count={reserveTotal}>
          {(deck.reserve_cards || []).length === 0 && (
            <Text style={styles.muted}>{t("교체 덱이 비어 있습니다.")}</Text>
          )}
          {(deck.reserve_cards || []).map((e, index) => (
            <View
              key={e.card_id}
              style={[
                editorStyles.reserveRow,
                index > 0 && editorStyles.divider,
              ]}
            >
              <Text
                style={[editorStyles.cardName, { flex: 1 }]}
                numberOfLines={1}
              >
                {nameOf(e.card_id)}
              </Text>
              <Stepper
                label={nameOf(e.card_id)}
                value={e.count}
                onChange={(v) => setReserve(e.card_id, v)}
              />
            </View>
          ))}
        </EditorSection>

        <EditorSection title="카드 추가">
          <Segmented
            value={zone}
            onChange={setZone}
            values={[
              { key: "cards", label: "기본 구성" },
              { key: "reserve", label: "교체 덱" },
            ]}
          />
          <SearchInput
            accessibilityLabel={t("추가할 카드 검색")}
            placeholder="카드명·번호 검색"
            value={query}
            onChangeText={setQuery}
          />
          {filtered.map((c, index) => {
            const count = inDeck(c.id);
            return (
              <View
                key={c.id}
                style={[editorStyles.addRow, index > 0 && editorStyles.divider]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={editorStyles.cardName} numberOfLines={1}>
                    {localized(c, language)}
                  </Text>
                  <Text style={styles.muted}>
                    {(c.code || "—") + " · " + t(c.type)}
                  </Text>
                </View>
                {count > 0 && <Badge label={"× " + count} tone="accent" />}
                <IconButton
                  icon="add"
                  label={localized(c, language) + " " + t("추가")}
                  filled
                  onPress={() => add(c.id)}
                />
              </View>
            );
          })}
        </EditorSection>

        <EditorSection title="편성 확인">
          {issues.length === 0 ? (
            <View style={editorStyles.issue}>
              <Icon name="checkmark-circle" size={18} color={colors.success} />
              <Text style={[styles.text, { flex: 1 }]}>
                {t("문제가 없습니다.")}
              </Text>
            </View>
          ) : (
            issues.map((issue, n) => (
              <View key={n} style={editorStyles.issue}>
                <Icon
                  name={issue.severity === "error" ? "alert-circle" : "warning"}
                  size={18}
                  color={
                    issue.severity === "error" ? colors.danger : colors.accent
                  }
                />
                <Text style={[styles.text, { flex: 1, fontSize: 14 }]}>
                  {t(issue.message)}
                </Text>
              </View>
            ))
          )}
        </EditorSection>

        <EditorSection title="덱 코드로 가져오기">
          <Input
            accessibilityLabel={t("가져올 덱 코드")}
            placeholder={t("가져올 덱 코드 붙여넣기")}
            value={importText}
            onChangeText={setImportText}
          />
          <Button
            label="가져오기"
            icon="download-outline"
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
        </EditorSection>
      </ScrollView>

      <View
        style={[editorStyles.bar, { paddingBottom: space.md + insets.bottom }]}
      >
        <View style={{ flex: 1 }}>
          <Text style={editorStyles.barTotal}>
            {total + " " + t("장")}
            {reserveTotal ? "  ·  " + t("교체 덱") + " " + reserveTotal : ""}
          </Text>
          <Text
            style={[
              styles.muted,
              errors.length > 0 && { color: colors.danger },
            ]}
            numberOfLines={1}
          >
            {errors.length > 0
              ? t("저장 전에 고쳐야 할 문제") + " " + errors.length
              : issues.length > 0
                ? t("확인할 항목") + " " + issues.length
                : t("저장할 수 있습니다.")}
          </Text>
        </View>
        <Button
          label="초안 저장"
          icon="save-outline"
          variant="primary"
          loading={busy}
          disabled={blocked}
          onPress={save}
        />
      </View>
    </View>
  );
}

function EditorSection({
  title,
  count,
  children,
}: {
  title: string;
  count?: number;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <View style={{ marginBottom: space.xl }}>
      <View style={editorStyles.sectionHeader}>
        <Text style={editorStyles.sectionTitle}>{t(title)}</Text>
        {count !== undefined && <Badge label={String(count)} tone="accent" />}
      </View>
      <View style={editorStyles.section}>{children}</View>
    </View>
  );
}

function FieldLabel({ text }: { text: string }) {
  const { t } = useApp();
  return <Text style={editorStyles.fieldLabel}>{t(text)}</Text>;
}

function ChipRow({ children }: { children: React.ReactNode }) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={{ gap: space.sm }}
      style={{ flexGrow: 0, marginBottom: space.md }}
    >
      {children}
    </ScrollView>
  );
}

const editorStyles = StyleSheet.create({
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    marginBottom: space.sm,
    marginLeft: space.xs,
  },
  sectionTitle: { color: colors.muted, fontSize: 13, fontWeight: "700" },
  section: {
    padding: space.lg,
    borderRadius: radius.lg,
    backgroundColor: colors.panel,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "600",
    marginBottom: 6,
  },
  labelRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  divider: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  cardRow: { paddingVertical: space.md, gap: space.sm },
  cardHead: { flexDirection: "row", alignItems: "center", gap: 6 },
  cardName: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "600",
    flexShrink: 1,
  },
  steppers: { flexDirection: "row", gap: space.sm },
  stepperCell: { flex: 1, gap: 4, alignItems: "flex-start" },
  stepperLabel: { color: colors.subtle, fontSize: 11, fontWeight: "600" },
  reserveRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingVertical: space.sm,
  },
  addRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.sm,
    paddingVertical: 6,
  },
  issue: {
    flexDirection: "row",
    gap: space.sm,
    alignItems: "flex-start",
    paddingVertical: 4,
  },
  bar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    paddingHorizontal: space.lg,
    paddingTop: space.md,
    backgroundColor: colors.panel,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  barTotal: { color: colors.text, fontSize: 17, fontWeight: "700" },
});
