import React from "react";
import { ScrollView } from "react-native";
import { router, type Href } from "expo-router";
import {
  EmptyState,
  ListRow,
  ListSection,
  colors,
  type IconName,
} from "../src/ui";

// 메인화면에 두기 애매한 부가 기능 모음.
// 루멘 파티는 아직 미공개라 화면은 유지하되 목록에서 숨긴다. 공개할 때 true로 바꾼다.
const PARTY_PUBLIC = false;

type Tool = {
  label: string;
  description: string;
  icon: IconName;
  href: string;
  visible: boolean;
};

const allTools: Tool[] = [
  {
    label: "루멘 파티",
    description: "2–4인 보드게임 모드",
    icon: "dice-outline",
    href: "/party",
    visible: PARTY_PUBLIC,
  },
];
const tools = allTools.filter((tool) => tool.visible);

export default function Utilities() {
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{
        width: "100%",
        maxWidth: 760,
        alignSelf: "center",
        padding: 16,
      }}
    >
      {tools.length === 0 ? (
        <EmptyState
          icon="construct-outline"
          title="준비 중인 기능이 곧 추가됩니다."
        />
      ) : (
        <ListSection>
          {tools.map((tool) => (
            <ListRow
              key={tool.href}
              icon={tool.icon}
              title={tool.label}
              subtitle={tool.description}
              onPress={() => router.push(tool.href as Href)}
            />
          ))}
        </ListSection>
      )}
    </ScrollView>
  );
}
