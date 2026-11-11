import React, { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useLocalSearchParams, router, Stack } from "expo-router";
import { useApp } from "../../src/provider";
import { localized } from "../../src/core";
import {
  Badge,
  CachedImage,
  EmptyState,
  Icon,
  ListRow,
  ListSection,
  RichText,
  colors,
  radius,
  space,
  styles,
  type as text,
} from "../../src/ui";
import { CardStats } from "../../src/card-stats";
import { CardImageViewer } from "../../src/card-image-viewer";
import { cardPrintings } from "../../src/collection-data";

export default function CardDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { catalog, language, t } = useApp();
  const { width } = useWindowDimensions();
  const [viewing, setViewing] = useState(false);
  const card = catalog?.cards.find((c) => c.id === Number(id));
  if (!card)
    return (
      <View style={styles.screen}>
        <EmptyState
          icon="alert-circle-outline"
          title="사용할 수 없는 카드가 있습니다."
        />
      </View>
    );
  const name = localized(card, language);
  const effect = localized(card, language, "text");
  const detail = localized(card, language, "detail_text");
  const character = catalog?.characters.find((c) => c.id === card.character_id);
  const qna = catalog?.qna.filter((q) => q.card_ids.includes(card.id)) || [];
  const printings = catalog ? cardPrintings(card.id, catalog) : [];
  const today = new Date(Date.now() + 9 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  // 카드 비율(약 1:1.4)을 유지하되 태블릿에서 지나치게 커지지 않게 한다.
  const imageWidth = Math.min(width - space.lg * 2, 360);
  const image = card.img || card.img_mid || card.img_sm;
  const tags = [card.pos, card.body, card.special].filter(Boolean);
  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={{ paddingBottom: 48 }}
    >
      <Stack.Screen options={{ title: name || "LumenDB" }} />
      <CardImageViewer
        url={viewing ? image : ""}
        title={name}
        onClose={() => setViewing(false)}
      />
      <Pressable
        accessibilityRole="imagebutton"
        accessibilityLabel={t("카드 이미지 크게 보기")}
        onPress={() => setViewing(true)}
        style={({ pressed }) => [
          detailStyles.image,
          { width: imageWidth },
          pressed && { opacity: 0.9 },
        ]}
      >
        <CachedImage
          url={card.img || card.img_mid}
          large
          height={imageWidth * 1.4}
        />
        <View style={detailStyles.zoomHint}>
          <Icon name="expand-outline" size={16} color={colors.text} />
        </View>
      </Pressable>

      <Text style={[text.display, { marginTop: space.lg }]}>{name}</Text>
      <View style={detailStyles.meta}>
        <Text style={styles.muted}>{card.code || "—"}</Text>
        {character && <Badge label={localized(character, language)} />}
        <Badge label={card.type} tone="accent" />
        {card.ultimate && <Badge label="얼티밋" tone="danger" />}
        {tags.map((tag) => (
          <Badge key={tag} label={tag} />
        ))}
      </View>

      <View style={{ marginTop: space.lg }}>
        <CardStats card={card} />
      </View>

      {!!effect && (
        <Section title="효과">
          <RichText text={effect} />
        </Section>
      )}
      {!!detail && (
        <Section title="보충 설명">
          <RichText text={detail} />
        </Section>
      )}

      <Text style={detailStyles.heading}>{t("수록 정보")}</Text>
      {printings.length === 0 ? (
        <View style={styles.panel}>
          <Text style={styles.muted}>{t("수록 정보가 없습니다.")}</Text>
        </View>
      ) : (
        printings.map((printing) => {
          const thumb = printing.items.find(
            (item) => item.img_sm || item.image,
          );
          const released = printing.pack?.released;
          const upcoming = !released || released > today;
          return (
            <View key={printing.key} style={[styles.panel, detailStyles.print]}>
              {!!thumb && (
                <CachedImage url={thumb.img_sm || thumb.image} height={96} />
              )}
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={text.heading} numberOfLines={2}>
                  {printing.pack
                    ? localized(printing.pack, language)
                    : t("팩 정보 없음")}
                </Text>
                <Text style={styles.muted}>
                  {t("수록번호") + " · " + (printing.code || "—")}
                </Text>
                <View style={detailStyles.meta}>
                  {printing.rarities.map((rarity) => (
                    <Badge key={rarity} label={rarity} tone="accent" />
                  ))}
                  <Badge label={printing.items[0]!.item_type} />
                  {upcoming && <Badge label="미발매" tone="danger" />}
                </View>
                {!!released && (
                  <Text style={styles.muted}>
                    {t("발매일") + " · " + released}
                  </Text>
                )}
              </View>
            </View>
          );
        })
      )}

      {qna.length > 0 && (
        <View style={{ marginTop: space.xl }}>
          <ListSection title={t("관련 Q&A") + " · " + qna.length}>
            {qna.map((q) => (
              <ListRow
                key={q.id}
                icon="chatbubble-ellipses-outline"
                title={q.title}
                subtitle={q.tags || undefined}
                onPress={() =>
                  router.push({ pathname: "/qna/[id]", params: { id: q.id } })
                }
              />
            ))}
          </ListSection>
        </View>
      )}
    </ScrollView>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <View>
      <Text style={detailStyles.heading}>{t(title)}</Text>
      <View style={styles.panel}>{children}</View>
    </View>
  );
}

const detailStyles = StyleSheet.create({
  image: {
    alignSelf: "center",
    borderRadius: radius.lg,
    overflow: "hidden",
  },
  zoomHint: {
    position: "absolute",
    right: space.sm,
    bottom: space.sm,
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: "rgba(0, 0, 0, 0.55)",
    alignItems: "center",
    justifyContent: "center",
  },
  meta: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: 6,
    marginTop: space.sm,
  },
  heading: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: "700",
    marginBottom: space.sm,
    marginTop: space.xl,
    marginLeft: space.xs,
  },
  print: { flexDirection: "row", gap: space.md, alignItems: "flex-start" },
});
