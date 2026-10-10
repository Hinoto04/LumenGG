import type * as SQLite from "expo-sqlite";
import type {
  Deck,
  Operation,
  QueueItem,
  SyncResponse,
  CalcState,
} from "./types";

let database: Promise<SQLite.SQLiteDatabase> | undefined;
let openDatabase: () => Promise<SQLite.SQLiteDatabase>;
let randomUUID: () => string;
export function configureStorage(
  factory: () => Promise<SQLite.SQLiteDatabase>,
  uuid: () => string,
) {
  database = undefined;
  writes = Promise.resolve();
  openDatabase = factory;
  randomUUID = uuid;
}
let writes: Promise<any> = Promise.resolve();
export function userDb() {
  if (!database)
    database = (async () => {
      const db = await openDatabase();
      await db.execAsync(`PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS documents(scope TEXT,entity TEXT,id TEXT,data TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0,dirty INTEGER NOT NULL DEFAULT 0,error TEXT,PRIMARY KEY(scope,entity,id));
      CREATE TABLE IF NOT EXISTS queue(seq INTEGER PRIMARY KEY AUTOINCREMENT,scope TEXT NOT NULL,entity TEXT NOT NULL,entity_id TEXT NOT NULL,revision INTEGER NOT NULL,operation TEXT NOT NULL,error TEXT);
      CREATE INDEX IF NOT EXISTS queue_scope ON queue(scope,seq);
      CREATE TABLE IF NOT EXISTS images(url TEXT PRIMARY KEY,path TEXT NOT NULL,size INTEGER NOT NULL,thumbnail INTEGER NOT NULL,touched INTEGER NOT NULL);`);
      return db;
    })();
  return database;
}
export async function write<T>(
  action: (db: SQLite.SQLiteDatabase) => Promise<T>,
): Promise<T> {
  const result = writes.then(async () => action(await userDb()));
  writes = result.catch(() => undefined);
  return result;
}
export async function preference<T>(key: string, fallback: T): Promise<T> {
  const row = await (
    await userDb()
  ).getFirstAsync<{ value: string }>(
    "SELECT value FROM preferences WHERE key=?",
    key,
  );
  return row ? JSON.parse(row.value) : fallback;
}
export function setPreference(key: string, value: any) {
  return write((db) =>
    db.runAsync(
      "INSERT OR REPLACE INTO preferences VALUES (?,?)",
      key,
      JSON.stringify(value),
    ),
  );
}
export async function documents<T>(
  scope: string,
  entity: string,
): Promise<T[]> {
  const rows = await (
    await userDb()
  ).getAllAsync<{ data: string; error: string | null }>(
    "SELECT data,error FROM documents WHERE scope=? AND entity=? ORDER BY id",
    scope,
    entity,
  );
  return rows.map((r) => ({ ...JSON.parse(r.data), sync_error: r.error }));
}
export async function saveDocument(
  scope: string,
  entity: "deck" | "collection",
  id: string,
  data: any,
  queue = true,
  action: "upsert" | "delete" = "upsert",
) {
  const operation: Operation = {
    operation_id: randomUUID(),
    entity,
    entity_id: entity === "collection" ? Number(id) : id,
    action,
    data,
  };
  return write(async (db) => {
    await db.withExclusiveTransactionAsync(async (tx) => {
      const current = await tx.getFirstAsync<{ revision: number }>(
        "SELECT revision FROM documents WHERE scope=? AND entity=? AND id=?",
        scope,
        entity,
        id,
      );
      const revision = (current?.revision || 0) + 1;
      await tx.runAsync(
        "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,?,1,NULL)",
        scope,
        entity,
        id,
        JSON.stringify(data),
        revision,
      );
      // A failed immutable operation is replaced only by a fresh user edit.
      await tx.runAsync(
        "DELETE FROM queue WHERE scope=? AND entity=? AND entity_id=? AND error IS NOT NULL",
        scope,
        entity,
        id,
      );
      if (queue && scope !== "guest")
        await tx.runAsync(
          "INSERT INTO queue(scope,entity,entity_id,revision,operation) VALUES (?,?,?,?,?)",
          scope,
          entity,
          id,
          revision,
          JSON.stringify(operation),
        );
    });
  });
}
export async function pending(scope: string): Promise<QueueItem[]> {
  const rows = await (
    await userDb()
  ).getAllAsync<{ seq: number; operation: string; error: string | null }>(
    "SELECT seq,operation,error FROM queue WHERE scope=? AND error IS NULL ORDER BY seq LIMIT 100",
    scope,
  );
  return rows.map((r) => ({ seq: r.seq, operation: JSON.parse(r.operation) }));
}
export async function mergeSnapshot(
  scope: string,
  response: SyncResponse,
  sent: QueueItem[],
) {
  return write(async (db) =>
    db.withExclusiveTransactionAsync(async (tx) => {
      for (const receipt of response.results || []) {
        const item = sent.find(
          (q) => q.operation.operation_id === receipt.operation_id,
        );
        if (!item) continue;
        const row = await tx.getFirstAsync<{ revision: number }>(
          "SELECT revision FROM queue WHERE seq=? AND scope=?",
          item.seq,
          scope,
        );
        if (!row) continue;
        if (receipt.ok) {
          await tx.runAsync(
            "DELETE FROM queue WHERE seq=? AND scope=?",
            item.seq,
            scope,
          );
          await tx.runAsync(
            "UPDATE documents SET dirty=0,error=NULL WHERE scope=? AND entity=? AND id=? AND revision=?",
            scope,
            item.operation.entity,
            String(item.operation.entity_id),
            row.revision,
          );
        } else {
          const error = JSON.stringify(receipt.error);
          await tx.runAsync(
            "UPDATE queue SET error=? WHERE seq=? AND scope=?",
            error,
            item.seq,
            scope,
          );
          await tx.runAsync(
            "UPDATE documents SET error=? WHERE scope=? AND entity=? AND id=? AND revision=?",
            error,
            scope,
            item.operation.entity,
            String(item.operation.entity_id),
            row.revision,
          );
        }
      }
      for (const [entity, items] of [
        ["deck", response.decks],
        ["collection", response.collection],
      ] as const) {
        const ids = new Set<string>();
        for (const item of items) {
          const id =
            entity === "deck"
              ? (item as Deck).uuid
              : String((item as { card_id: number }).card_id);
          ids.add(id);
          const existing = await tx.getFirstAsync<{ dirty: number }>(
            "SELECT dirty FROM documents WHERE scope=? AND entity=? AND id=?",
            scope,
            entity,
            id,
          );
          if (existing?.dirty) continue;
          await tx.runAsync(
            "INSERT OR REPLACE INTO documents VALUES (?,?,?,?,0,0,NULL)",
            scope,
            entity,
            id,
            JSON.stringify(item),
          );
        }
        const clean = await tx.getAllAsync<{ id: string }>(
          "SELECT id FROM documents WHERE scope=? AND entity=? AND dirty=0",
          scope,
          entity,
        );
        for (const row of clean)
          if (!ids.has(row.id))
            await tx.runAsync(
              "DELETE FROM documents WHERE scope=? AND entity=? AND id=?",
              scope,
              entity,
              row.id,
            );
      }
    }),
  );
}
export async function saveCalculator(state: CalcState) {
  return setPreference("local-calculator", state);
}
export async function eraseScope(scope: string) {
  return write(async (db) =>
    db.withExclusiveTransactionAsync(async (tx) => {
      await tx.runAsync("DELETE FROM documents WHERE scope=?", scope);
      await tx.runAsync("DELETE FROM queue WHERE scope=?", scope);
    }),
  );
}
export async function importGuest(
  scope: string,
  selectedCollectionIds: number[],
) {
  const collection = await documents<{ card_id: number; amount: number }>(
    "guest",
    "collection",
  );
  for (const item of collection.filter((c) =>
    selectedCollectionIds.includes(c.card_id),
  ))
    await saveDocument(scope, "collection", String(item.card_id), item);
}

// Preserve old drafts privately, but never send old deck edits after upgrading.
export function disableDeckWrites() {
  return write((db) =>
    db.withExclusiveTransactionAsync(async (tx) => {
      await tx.runAsync(`INSERT OR REPLACE INTO documents(scope,entity,id,data,revision,dirty,error)
      SELECT scope,'legacy_deck',id,data,revision,0,error FROM documents WHERE entity='deck' AND dirty=1`);
      await tx.runAsync("DELETE FROM queue WHERE entity='deck'");
      await tx.runAsync(
        "DELETE FROM documents WHERE entity='deck' AND dirty=1",
      );
    }),
  );
}
