import type { Catalog, CollectionItem } from "./types";
import { localized } from "./core";

/**
 * 컬렉션 목록 내보내기. 화면에 보이는 검색·필터·정렬 결과를 그대로 내보낸다.
 * 웹(`collection/export.py`)과 같은 형식을 만든다. 둘 중 하나를 바꾸면 다른 쪽도 맞춘다.
 */
export type ExportFormat = "txt" | "csv";
export interface ExportOptions {
  format: ExportFormat;
  /** 카드명은 항상 들어가고, 나머지 열은 끌 수 있다. */
  code: boolean;
  rare: boolean;
  amount: boolean;
}
export const defaultExportOptions: ExportOptions = {
  format: "txt",
  code: true,
  rare: true,
  amount: true,
};
export interface ExportEntry {
  name: string;
  code: string;
  rare: string;
  amount: number;
}
export interface ExportHeaders {
  name: string;
  code: string;
  rare: string;
  amount: string;
}
export const koreanExportHeaders: ExportHeaders = {
  name: "카드명",
  code: "코드",
  rare: "레어도",
  amount: "갯수",
};

/** 컬렉션 화면의 행(이미 검색·필터·정렬된 순서)을 내보낼 항목으로 바꾼다. */
export function collectionExportEntries(
  rows: CollectionItem[],
  catalog: Pick<Catalog, "cards">,
  amounts: Record<number, number>,
  language: string,
): ExportEntry[] {
  const cards = new Map(catalog.cards.map((card) => [card.id, card]));
  return rows.map((item) => {
    const card = item.card_id === null ? undefined : cards.get(item.card_id);
    return {
      name: (card ? localized(card, language) : "") || item.name,
      code: item.code,
      rare: item.rare,
      amount: Math.max(0, amounts[item.id] || 0),
    };
  });
}

/** 쉼표·따옴표·줄바꿈이 있으면 따옴표로 감싸고 안의 따옴표는 두 번 쓴다(RFC 4180). */
export function csvField(value: string): string {
  return /[",\r\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
}

function columns(options: ExportOptions) {
  return (["name", "code", "rare", "amount"] as const).filter(
    (key) => key === "name" || options[key],
  );
}

/**
 * 내보낼 파일 내용을 만든다.
 * - csv: 엑셀에서 한글이 깨지지 않게 UTF-8 BOM으로 시작하고, 머리글 행과 CRLF 줄바꿈을 쓴다.
 * - txt: 한 줄에 한 항목. 예) `번개 [ST1-001] (SR) x2`
 */
export function formatCollectionExport(
  entries: ExportEntry[],
  options: ExportOptions,
  headers: ExportHeaders = koreanExportHeaders,
): string {
  const keys = columns(options);
  if (options.format === "csv") {
    const lines = [
      keys.map((key) => csvField(headers[key])),
      ...entries.map((entry) =>
        keys.map((key) => csvField(String(entry[key]))),
      ),
    ].map((fields) => fields.join(","));
    return "\uFEFF" + lines.join("\r\n") + "\r\n";
  }
  return entries
    .map((entry) => {
      let line = entry.name;
      if (options.code && entry.code) line += ` [${entry.code}]`;
      if (options.rare && entry.rare) line += ` (${entry.rare})`;
      if (options.amount) line += ` x${entry.amount}`;
      return line + "\n";
    })
    .join("");
}

/** 예) lumen-favorites-20261119.csv */
export function collectionExportFileName(
  format: ExportFormat,
  date: Date = new Date(),
): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `lumen-favorites-${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}.${format}`;
}

export function exportMimeType(format: ExportFormat): string {
  return format === "csv" ? "text/csv" : "text/plain";
}
