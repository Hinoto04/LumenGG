import React from "react";
import { StyleSheet, Text, View } from "react-native";
import { useApp } from "./provider";
import { colors, space } from "./ui";

/**
 * 설정 화면의 한 묶음. 시뮬레이터 메뉴(play/src/components/SystemUi.tsx의 GameMenu)처럼
 * 위쪽 구분선으로 묶음을 나누고, 작은 제목을 붙인다.
 */
export function SettingSection({
  title,
  footer,
  first = false,
  children,
}: {
  title?: string;
  footer?: string;
  /** 맨 위 묶음은 구분선을 그리지 않는다. */
  first?: boolean;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <View style={[rowStyles.section, first && rowStyles.first]}>
      {!!title && <Text style={rowStyles.sectionTitle}>{t(title)}</Text>}
      {children}
      {!!footer && <Text style={rowStyles.footer}>{t(footer)}</Text>}
    </View>
  );
}

/**
 * "제목 + 작은 설명 | 오른쪽 조작" 한 줄. 조작이 넓으면 below에 넣어 제목 아래 전체 폭으로 놓는다.
 */
export function SettingRow({
  title,
  description,
  danger = false,
  children,
  below,
}: {
  title: string;
  description?: string;
  danger?: boolean;
  /** 오른쪽 조작. */
  children?: React.ReactNode;
  /** 제목 아래 전체 폭 조작. */
  below?: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <View style={rowStyles.row}>
      <View style={rowStyles.line}>
        <View style={rowStyles.text}>
          <Text style={[rowStyles.title, danger && { color: colors.danger }]}>
            {t(title)}
          </Text>
          {!!description && (
            <Text style={rowStyles.description}>{t(description)}</Text>
          )}
        </View>
        {children}
      </View>
      {below}
    </View>
  );
}

/** 설정 내용을 가운데에 일정 폭으로 모은다(가로 화면에서 줄이 너무 길어지지 않게). */
export function SettingColumn({ children }: { children: React.ReactNode }) {
  return <View style={rowStyles.column}>{children}</View>;
}

const rowStyles = StyleSheet.create({
  column: { width: "100%", maxWidth: 760, alignSelf: "center" },
  section: {
    gap: space.md,
    paddingTop: space.lg,
    marginTop: space.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.line,
  },
  first: { borderTopWidth: 0, paddingTop: 0, marginTop: 0 },
  sectionTitle: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
  },
  row: { gap: space.sm },
  line: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.lg,
    minHeight: 44,
  },
  text: { flex: 1, gap: 2 },
  title: { color: colors.text, fontSize: 15, fontWeight: "600" },
  description: { color: colors.muted, fontSize: 12, lineHeight: 17 },
  footer: { color: colors.subtle, fontSize: 12 },
});
