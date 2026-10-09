import React from "react";
import { ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useApp } from "../../src/provider";
import { localized } from "../../src/core";
import { styles, CachedImage, RichText, Button } from "../../src/ui";
import { cardPrintings } from "../../src/collection-data";
export default function CardDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { catalog, language, t } = useApp();
  const card = catalog?.cards.find((c) => c.id === Number(id));
  if (!card)
    return (
      <View style={styles.screen}>
        <Text style={styles.text}>{t("사용할 수 없는 카드가 있습니다.")}</Text>
      </View>
    );
  const qna = catalog?.qna.filter((q) => q.card_ids.includes(card.id));
  const printings = catalog ? cardPrintings(card.id, catalog) : [];
  const today = new Date(Date.now() + 9 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 40 }}
    >
      <Text style={styles.title}>{localized(card, language)}</Text>
      <Text style={styles.muted}>{card.code}</Text>
      <CachedImage url={card.img || card.img_mid} large height={420} />
      <View style={styles.panel}>
        <Text style={styles.text}>
          {t(card.type)} · {t(card.pos || "")} · {t(card.body || "")} ·{" "}
          {t(card.special || "")}
        </Text>
        <Text style={styles.text}>
          {t("속도")} {card.frame ?? "—"} · {t("대미지")} {card.damage ?? "—"}
        </Text>
        <Text style={styles.text}>
          Hit {card.hit} / Guard {card.guard} / Counter {card.counter}
        </Text>
        {card.type.includes("수비") && (
          <Text style={styles.text}>
            {t("상단")} {card.g_top || "—"} · {t("중단")} {card.g_mid || "—"} ·{" "}
            {t("하단")} {card.g_bot || "—"}
          </Text>
        )}
        <RichText text={localized(card, language, "text")} />
      </View>
      <View style={styles.panel}>
        <Text style={styles.text}>{t("보충 설명")}</Text>
        <RichText text={localized(card, language, "detail_text")} />
      </View>
      <Text style={styles.title}>{t("수록 정보")}</Text>
      {!printings.length && (
        <View style={styles.panel}>
          <Text style={styles.muted}>{t("수록 정보가 없습니다.")}</Text>
        </View>
      )}
      {printings.map((printing) => {
        const image = printing.items.find((item) => item.img_sm || item.image);
        const released = printing.pack?.released;
        return (
          <View key={printing.key} style={styles.panel}>
            <View style={styles.row}>
              {!!image && (
                <CachedImage url={image.img_sm || image.image} height={110} />
              )}
              <View style={{ flex: 1 }}>
                <Text style={[styles.text, { fontWeight: "700" }]}>
                  {printing.pack
                    ? localized(printing.pack, language)
                    : t("팩 정보 없음")}
                </Text>
                <Text style={[styles.text, { marginTop: 6 }]}>
                  {t("수록번호")} · {printing.code || "—"}
                </Text>
                <Text style={styles.muted}>
                  {t("레어도")} · {printing.rarities.join(" · ") || "—"}
                </Text>
                <Text style={styles.muted}>
                  {t("발매일")} ·{" "}
                  {released && released <= today
                    ? released
                    : `${t("미발매")}${released ? ` · ${released}` : ""}`}
                </Text>
                <Text style={styles.muted}>
                  {t(printing.items[0]!.item_type)}
                </Text>
              </View>
            </View>
          </View>
        );
      })}
      <Text style={styles.title}>Q&A</Text>
      {qna?.map((q) => (
        <View key={q.id} style={styles.panel}>
          <Text style={styles.text}>{q.title}</Text>
          <Button
            label="자세히"
            onPress={() =>
              router.push({ pathname: "/qna/[id]", params: { id: q.id } })
            }
          />
        </View>
      ))}
    </ScrollView>
  );
}
