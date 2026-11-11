import { PixelRatio, useWindowDimensions } from "react-native";

/**
 * 현재 창 크기에 따른 배치 정보. useWindowDimensions를 쓰므로 가로·세로를 돌리면 다시 계산된다.
 */
export function useScreen() {
  const { width, height } = useWindowDimensions();
  return {
    width,
    height,
    landscape: width > height,
    /** 폼·글 위주 화면의 최대 폭. 가로 화면에서 줄이 지나치게 길어지지 않게 한다. */
    readable: Math.min(width, 760),
  };
}

/**
 * 칸 하나가 대략 target 폭(dp)이 되도록 칸 수를 정한다.
 * 세로에서 보던 칸 크기를 가로에서도 유지해 한 화면에 더 많은 항목을 보여 준다.
 */
export function columnsFor(width: number, target: number, min = 1, max = 8) {
  return Math.min(max, Math.max(min, Math.round(width / target)));
}

/** 목록형 화면(덱·컬렉션·QNA·대회)의 칸 수. 한 칸이 너무 좁아지지 않게 300dp 이상을 유지한다. */
export function listColumns(width: number) {
  return Math.max(1, Math.min(3, Math.floor(width / 300)));
}

/**
 * 다칸 FlatList 한 칸의 스타일. 마지막 줄 칸이 혼자 남아도 다른 칸과 같은 폭을 유지한다.
 * padding은 화면 좌우 여백 합, gap은 칸 사이 간격이다.
 */
export function cellStyle(
  width: number,
  columns: number,
  gap = 12,
  padding = 32,
) {
  if (columns <= 1) return undefined;
  return {
    flex: 1,
    maxWidth: (width - padding - gap * (columns - 1)) / columns,
  };
}

/**
 * 카드 이미지 세 가지(img_sm 164px, img_mid 246px, img 821px 폭) 중 칸 크기에 맞는 것을 고른다.
 * 실제 화소 폭이 이미지보다 많이 크면 한 단계 큰 이미지를 쓴다. 원본은 용량이 커서 큰 칸에만 쓴다.
 */
export function cardImageFor(
  card: { img_sm?: string; img_mid?: string; img?: string },
  widthDp: number,
) {
  const pixels = PixelRatio.getPixelSizeForLayoutSize(widthDp);
  if (pixels > 700) return card.img || card.img_mid || card.img_sm || "";
  if (pixels > 330) return card.img_mid || card.img_sm || card.img || "";
  return card.img_sm || card.img_mid || card.img || "";
}
