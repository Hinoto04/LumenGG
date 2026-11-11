import React from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useApp } from "./provider";
import { localized } from "./core";
import {
  CachedImage,
  Icon,
  IconButton,
  colors,
  radius,
  space,
  tapFeedback,
} from "./ui";
import type { Character } from "./types";

/** 캐릭터 얼굴을 둥글게 잘라 보여 준다. 캐릭터가 없으면 물음표를 그린다. */
export function CharacterAvatar({
  character,
  size = 56,
  selected = false,
  dim = false,
  ring = colors.accent,
}: {
  character?: Character | null;
  size?: number;
  selected?: boolean;
  dim?: boolean;
  /** 선택 테두리 색. */
  ring?: string;
}) {
  const { language } = useApp();
  const initial = character ? localized(character, language).slice(0, 1) : "";
  return (
    <View
      style={[
        avatarStyles.frame,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          borderWidth: selected ? 3 : StyleSheet.hairlineWidth,
          borderColor: selected ? ring : colors.line,
        },
        dim && { opacity: 0.45 },
      ]}
    >
      {character ? (
        <>
          {/* 얼굴 이미지가 없거나 비어 있으면 이름 첫 글자가 보인다. */}
          <Text
            style={[avatarStyles.initial, { fontSize: size * 0.4 }]}
            importantForAccessibility="no"
          >
            {initial}
          </Text>
          {!!(character.img_sm || character.img) && (
            <View style={avatarStyles.cover}>
              <CachedImage
                url={character.img_sm || character.img}
                fill
                height={size}
                transparent
              />
            </View>
          )}
        </>
      ) : (
        <Icon name="help" size={size * 0.45} color={colors.subtle} />
      )}
    </View>
  );
}

/** 얼굴 + 이름 타일 하나. 격자와 가로 줄 모두에서 쓴다. */
function CharacterTile({
  character,
  label,
  selected,
  size,
  width,
  onPress,
  allIcon = false,
}: {
  character?: Character | null;
  label: string;
  selected: boolean;
  size: number;
  width: number;
  onPress: () => void;
  allIcon?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={label}
      accessibilityState={{ checked: selected }}
      onPress={() => {
        tapFeedback("selection");
        onPress();
      }}
      style={({ pressed }) => [
        avatarStyles.tile,
        { width },
        pressed && { opacity: 0.75, transform: [{ scale: 0.96 }] },
      ]}
    >
      {allIcon ? (
        <View
          style={[
            avatarStyles.frame,
            avatarStyles.all,
            {
              width: size,
              height: size,
              borderRadius: size / 2,
              borderWidth: selected ? 3 : StyleSheet.hairlineWidth,
              borderColor: selected ? colors.accent : colors.line,
            },
          ]}
        >
          <Icon
            name="apps"
            size={size * 0.4}
            color={selected ? colors.accent : colors.muted}
          />
        </View>
      ) : (
        <CharacterAvatar
          character={character}
          size={size}
          selected={selected}
        />
      )}
      <Text
        numberOfLines={1}
        style={[
          avatarStyles.name,
          selected && { color: colors.accent, fontWeight: "700" },
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

/**
 * 캐릭터 얼굴 격자. value는 캐릭터 id 문자열이고, allLabel을 주면 맨 앞에 "전체"(빈 값) 칸을 둔다.
 * columns를 생략하면 주어진 폭에 맞춰 칸 수를 정한다.
 */
export function CharacterGrid({
  characters,
  value,
  onChange,
  allLabel,
  width,
  size = 56,
  horizontal = false,
}: {
  characters: Character[];
  value: string;
  onChange: (id: string) => void;
  allLabel?: string;
  /** 격자를 놓을 가로 폭. 칸 수 계산에 쓴다. */
  width: number;
  size?: number;
  /** 한 줄 가로 스크롤로 보여 준다. */
  horizontal?: boolean;
}) {
  const { language, t } = useApp();
  const tileWidth = size + 16;
  const gap = space.sm;
  const columns = Math.max(3, Math.floor((width + gap) / (tileWidth + gap)));
  // 남는 폭을 칸 사이에 고르게 나눈다.
  // 소수점 반올림으로 마지막 칸이 다음 줄로 밀리지 않게 내림한다.
  const cell = horizontal
    ? tileWidth
    : Math.floor((width - gap * (columns - 1)) / columns);
  const tiles = [
    ...(allLabel !== undefined
      ? [
          <CharacterTile
            key="all"
            label={t(allLabel)}
            selected={!value}
            size={size}
            width={cell}
            allIcon
            onPress={() => onChange("")}
          />,
        ]
      : []),
    ...characters.map((c) => (
      <CharacterTile
        key={c.id}
        character={c}
        label={localized(c, language)}
        selected={value === String(c.id)}
        size={size}
        width={cell}
        onPress={() => onChange(String(c.id))}
      />
    )),
  ];
  if (horizontal)
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ gap, paddingHorizontal: space.lg }}
        accessibilityRole="radiogroup"
      >
        {tiles}
      </ScrollView>
    );
  return (
    <View
      accessibilityRole="radiogroup"
      style={{
        flexDirection: "row",
        flexWrap: "wrap",
        columnGap: gap,
        rowGap: space.md,
      }}
    >
      {tiles}
    </View>
  );
}

/** 캐릭터 얼굴 격자를 띄우는 아래쪽 시트. 하나를 고르면 바로 닫힌다. */
/** 화면 아래에서 올라오는 시트. 바깥을 누르거나 뒤로 가기로 닫힌다. */
export function BottomSheet({
  visible,
  title,
  onClose,
  header,
  children,
}: {
  visible: boolean;
  title: string;
  onClose: () => void;
  /** 제목 아래, 스크롤 영역 위에 고정되는 조작(검색창·탭 등). */
  header?: React.ReactNode;
  children: (width: number) => React.ReactNode;
}) {
  const { t } = useApp();
  const insets = useSafeAreaInsets();
  const { width, height } = useWindowDimensions();
  const sheetWidth = Math.min(width, 720);
  return (
    <Modal
      visible={visible}
      transparent
      statusBarTranslucent
      animationType="slide"
      supportedOrientations={["portrait", "landscape"]}
      onRequestClose={onClose}
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t("닫기")}
        onPress={onClose}
        style={avatarStyles.backdrop}
      />
      <View
        style={[
          avatarStyles.sheet,
          {
            width: sheetWidth,
            maxHeight: height * 0.85,
            paddingBottom: insets.bottom + space.lg,
          },
        ]}
      >
        <View style={avatarStyles.handle} />
        <View style={avatarStyles.sheetHeader}>
          <Text style={avatarStyles.sheetTitle}>{t(title)}</Text>
          <IconButton icon="close" label="닫기" onPress={onClose} />
        </View>
        {header && (
          <View style={{ paddingHorizontal: space.lg }}>{header}</View>
        )}
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ paddingHorizontal: space.lg }}
        >
          {children(sheetWidth - space.lg * 2)}
        </ScrollView>
      </View>
    </Modal>
  );
}

/** 캐릭터 얼굴 격자를 띄우는 아래쪽 시트. 하나를 고르면 바로 닫힌다. */
export function CharacterPickerSheet({
  visible,
  title,
  characters,
  value,
  onSelect,
  onClose,
}: {
  visible: boolean;
  title: string;
  characters: Character[];
  value: string;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  return (
    <BottomSheet visible={visible} title={title} onClose={onClose}>
      {(width) => (
        <CharacterGrid
          characters={characters}
          value={value}
          width={width}
          size={60}
          onChange={(id) => {
            onSelect(id);
            onClose();
          }}
        />
      )}
    </BottomSheet>
  );
}

/**
 * 대전·계산기에서 한쪽 플레이어를 나타내는 칸. 누르면 캐릭터(또는 덱)를 바꾸는 선택 화면을 연다.
 */
export function PlayerSlot({
  label,
  character,
  title,
  subtitle,
  onPress,
  accent = colors.accent,
  size = 84,
  children,
}: {
  label: string;
  character?: Character | null;
  /** 큰 글씨 이름. 생략하면 캐릭터 이름. */
  title?: string;
  subtitle?: string;
  onPress?: () => void;
  accent?: string;
  size?: number;
  /** 이름 아래에 붙는 추가 조작(특성 선택 등). */
  children?: React.ReactNode;
}) {
  const { language, t } = useApp();
  const name =
    title ?? (character ? localized(character, language) : t("선택"));
  return (
    <View style={[avatarStyles.slot, { borderColor: accent }]}>
      <Text style={[avatarStyles.slotLabel, { color: accent }]}>
        {t(label)}
      </Text>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t(label) + " · " + name}
        accessibilityHint={t("눌러서 바꿉니다.")}
        disabled={!onPress}
        onPress={() => {
          tapFeedback();
          onPress?.();
        }}
        style={({ pressed }) => [
          avatarStyles.slotButton,
          pressed && { opacity: 0.8, transform: [{ scale: 0.97 }] },
        ]}
      >
        <View>
          <CharacterAvatar
            character={character}
            size={size}
            selected
            ring={accent}
          />
          {!!onPress && (
            <View style={[avatarStyles.swap, { backgroundColor: accent }]}>
              <Icon name="swap-horizontal" size={14} color={colors.onAccent} />
            </View>
          )}
        </View>
        <Text numberOfLines={1} style={avatarStyles.slotName}>
          {name}
        </Text>
        {!!subtitle && (
          <Text numberOfLines={1} style={avatarStyles.slotSub}>
            {subtitle}
          </Text>
        )}
      </Pressable>
      {children}
    </View>
  );
}

/** 두 PlayerSlot 사이의 VS 표시. */
export function Versus() {
  return (
    <View style={avatarStyles.versus}>
      <Text style={avatarStyles.versusText}>VS</Text>
    </View>
  );
}

const avatarStyles = StyleSheet.create({
  frame: {
    overflow: "hidden",
    backgroundColor: colors.surface2,
    alignItems: "center",
    justifyContent: "center",
  },
  all: { backgroundColor: colors.panel },
  initial: { color: colors.muted, fontWeight: "800" },
  cover: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  tile: { alignItems: "center", gap: 6 },
  name: { color: colors.text, fontSize: 12, textAlign: "center" },
  backdrop: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.55)",
  },
  sheet: {
    position: "absolute",
    bottom: 0,
    alignSelf: "center",
    backgroundColor: colors.panel,
    borderTopLeftRadius: radius.lg + 4,
    borderTopRightRadius: radius.lg + 4,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.line,
    marginTop: space.sm,
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    paddingLeft: space.lg,
    paddingRight: space.sm,
    paddingVertical: space.xs,
  },
  sheetTitle: { flex: 1, color: colors.text, fontSize: 18, fontWeight: "700" },
  slot: {
    flex: 1,
    alignItems: "center",
    gap: space.sm,
    padding: space.md,
    borderRadius: radius.lg,
    borderWidth: 1,
    backgroundColor: colors.panel,
  },
  slotLabel: { fontSize: 12, fontWeight: "800", letterSpacing: 1 },
  slotButton: { alignItems: "center", gap: 4 },
  swap: {
    position: "absolute",
    right: -2,
    bottom: -2,
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: colors.panel,
  },
  slotName: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
    maxWidth: 220,
  },
  slotSub: { color: colors.muted, fontSize: 12, maxWidth: 220 },
  versus: {
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 2,
  },
  versusText: {
    color: colors.accent,
    fontSize: 22,
    fontWeight: "900",
    fontStyle: "italic",
    letterSpacing: 1,
  },
});
