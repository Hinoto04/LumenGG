import * as SQLite from "expo-sqlite";
import * as FileSystem from "expo-file-system/legacy";
import { File } from "expo-file-system";
import { Asset } from "expo-asset";
import * as Crypto from "expo-crypto";
import type { Catalog, Manifest } from "./types";
import { BASE_URL, request, absoluteUrl } from "./api";
import { preference, setPreference, userDb, write } from "./storage";

const directory = FileSystem.documentDirectory + "catalogs/";
const imageDirectory = FileSystem.documentDirectory + "images/";
const inFlightImages = new Map<string, Promise<string>>();
let refreshFlight: Promise<Catalog | null> | null = null;
export async function readCatalog(name: string): Promise<Catalog> {
  const db = await SQLite.openDatabaseAsync(
    name,
    { useNewConnection: true },
    directory,
  );
  try {
    const integrity =
      await db.getFirstAsync<Record<string, string>>("PRAGMA quick_check");
    if (
      !integrity ||
      Object.values(integrity)[0] !== "ok" ||
      (await db.getAllAsync("PRAGMA foreign_key_check")).length
    )
      throw new Error("Invalid catalog integrity.");
    const schema = await db.getFirstAsync<{ value: string }>(
      "SELECT value FROM metadata WHERE key='schema_version'",
    );
    const version = await db.getFirstAsync<{ value: string }>(
      "SELECT value FROM metadata WHERE key='release_version'",
    );
    if (schema?.value !== "1" || !version)
      throw new Error("Unsupported catalog schema.");
    const rows = await db.getAllAsync<{
      kind: string;
      id: number;
      data: string;
      search: string;
    }>("SELECT kind,id,data,search FROM entries ORDER BY id");
    const groups: Record<string, any[]> = {};
    for (const row of rows)
      (groups[row.kind] ??= []).push({
        ...JSON.parse(row.data),
        search: row.search,
      });
    if (!groups.card?.length || !groups.character?.length || !groups.rules?.[0])
      throw new Error("Incomplete catalog.");
    return {
      version: version.value,
      cards: groups.card,
      characters: groups.character,
      packs: groups.pack || [],
      collection: groups.collection || [],
      qna: groups.qna || [],
      rules: groups.rules[0],
    };
  } finally {
    await db.closeAsync();
  }
}
export async function bootstrapCatalog(): Promise<Catalog> {
  await FileSystem.makeDirectoryAsync(directory, { intermediates: true });
  const active = await preference<string | null>("catalog-active", null);
  if (active) {
    try {
      return await readCatalog(active);
    } catch {
      await setPreference("catalog-manifest", null);
      /* Recover using the previous verified DB. */
    }
  }
  const previous = await preference<string | null>("catalog-previous", null);
  if (previous) {
    try {
      const data = await readCatalog(previous);
      await setPreference("catalog-active", previous);
      await setPreference("catalog-manifest", null);
      return data;
    } catch {}
  }
  const asset = Asset.fromModule(require("../assets/catalog.sqlite"));
  await asset.downloadAsync();
  if (!asset.localUri) throw new Error("Bundled catalog unavailable.");
  await FileSystem.copyAsync({
    from: asset.localUri,
    to: directory + "seed.sqlite",
  });
  const data = await readCatalog("seed.sqlite");
  await setPreference("catalog-active", "seed.sqlite");
  await setPreference("catalog-manifest", null);
  return data;
}
export async function updateCatalog(force = false): Promise<Catalog | null> {
  if (refreshFlight) return refreshFlight;
  refreshFlight = (async () => {
    const last = await preference<number>("catalog-checked", 0);
    if (!force && Date.now() - last < 300000) return null;
    await setPreference("catalog-checked", Date.now());
    const manifest: Manifest = await request(
      "/catalog/manifest?client_version=1.0.0&schema_version=1",
      {},
      false,
    );
    if (
      manifest.schema_version !== 1 ||
      !/^\d{8}T\d{6}-[a-f0-9]{12}$/.test(manifest.release_version) ||
      !/^[a-f0-9]{64}$/.test(manifest.sha256)
    )
      throw new Error("Invalid catalog manifest.");
    const metadata = await preference<Manifest | null>(
      "catalog-manifest",
      null,
    );
    if (metadata?.release_version === manifest.release_version) return null;
    const filename =
      manifest.release_version + "-" + Crypto.randomUUID() + ".sqlite";
    const temporary = directory + filename + ".part";
    try {
      const download = absoluteUrl(manifest.download_url);
      if (new URL(download).origin !== new URL(BASE_URL).origin)
        throw new Error("Untrusted catalog origin.");
      await FileSystem.downloadAsync(download, temporary);
      const info = await FileSystem.getInfoAsync(temporary);
      if (!info.exists || info.size !== manifest.size_bytes)
        throw new Error("Incomplete catalog download.");
      const hash = new Uint8Array(
        await Crypto.digest(
          Crypto.CryptoDigestAlgorithm.SHA256,
          await new File(temporary).bytes(),
        ),
      );
      const hex = Array.from(hash, (b) => b.toString(16).padStart(2, "0")).join(
        "",
      );
      if (hex !== manifest.sha256)
        throw new Error("Catalog checksum mismatch.");
      await FileSystem.moveAsync({ from: temporary, to: directory + filename });
      const catalog = await readCatalog(filename);
      if (catalog.version !== manifest.release_version)
        throw new Error("Catalog version mismatch.");
      await write(async (db) =>
        db.withExclusiveTransactionAsync(async (tx) => {
          const current = await tx.getFirstAsync<{ value: string }>(
            "SELECT value FROM preferences WHERE key='catalog-active'",
          );
          if (current)
            await tx.runAsync(
              "INSERT OR REPLACE INTO preferences VALUES (?,?)",
              "catalog-previous",
              current.value,
            );
          await tx.runAsync(
            "INSERT OR REPLACE INTO preferences VALUES (?,?)",
            "catalog-active",
            JSON.stringify(filename),
          );
          await tx.runAsync(
            "INSERT OR REPLACE INTO preferences VALUES (?,?)",
            "catalog-manifest",
            JSON.stringify(manifest),
          );
          await tx.runAsync(
            "INSERT OR REPLACE INTO preferences VALUES (?,?)",
            "catalog-updated",
            JSON.stringify(Date.now()),
          );
        }),
      );
      return catalog;
    } finally {
      await FileSystem.deleteAsync(temporary, { idempotent: true });
    }
  })().finally(() => {
    refreshFlight = null;
  });
  return refreshFlight;
}
export async function cachedImage(
  url: string,
  thumbnail = true,
): Promise<string> {
  if (!url) return "";
  const absolute = absoluteUrl(url),
    db = await userDb();
  const existing = await db.getFirstAsync<{ path: string }>(
    "SELECT path FROM images WHERE url=?",
    absolute,
  );
  if (existing && (await FileSystem.getInfoAsync(existing.path)).exists) {
    await write((d) =>
      d.runAsync(
        "UPDATE images SET touched=?,thumbnail=MAX(thumbnail,?) WHERE url=?",
        Date.now(),
        thumbnail ? 1 : 0,
        absolute,
      ),
    );
    return existing.path;
  }
  if (inFlightImages.has(absolute)) return inFlightImages.get(absolute)!;
  const flight = (async () => {
    await FileSystem.makeDirectoryAsync(imageDirectory, {
      intermediates: true,
    });
    const name = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      absolute,
    );
    const path = imageDirectory + name;
    const result = await FileSystem.downloadAsync(absolute, path);
    if (result.status !== 200) {
      await FileSystem.deleteAsync(path, { idempotent: true });
      throw new Error("Image unavailable.");
    }
    const info = await FileSystem.getInfoAsync(path);
    if (!info.exists) throw new Error("Image unavailable.");
    await write((d) =>
      d.runAsync(
        "INSERT OR REPLACE INTO images VALUES (?,?,?,?,?)",
        absolute,
        path,
        info.size,
        thumbnail ? 1 : 0,
        Date.now(),
      ),
    );
    if (!thumbnail) await trimImages();
    return path;
  })().finally(() => inFlightImages.delete(absolute));
  inFlightImages.set(absolute, flight);
  return flight;
}
export async function cacheThumbnails(catalog: Catalog) {
  const urls = [
    ...new Set(
      [...catalog.cards, ...catalog.characters, ...catalog.collection]
        .map((c) => c.img_sm)
        .filter(Boolean),
    ),
  ];
  let index = 0;
  await Promise.all(
    Array.from({ length: 3 }, async () => {
      while (index < urls.length) {
        const url = urls[index++];
        if (url) await cachedImage(url, true).catch(() => undefined);
      }
    }),
  );
}
export async function trimImages(clear = false) {
  const db = await userDb();
  const files = await db.getAllAsync<{
    url: string;
    path: string;
    size: number;
  }>("SELECT url,path,size FROM images WHERE thumbnail=0 ORDER BY touched");
  let total = files.reduce((s, f) => s + f.size, 0);
  for (const file of files) {
    if (!clear && total <= 300 * 1024 * 1024) break;
    await FileSystem.deleteAsync(file.path, { idempotent: true });
    await write((d) =>
      d.runAsync("DELETE FROM images WHERE url=? AND thumbnail=0", file.url),
    );
    total -= file.size;
  }
}
