import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";
import {
  configureStorage,
  saveDocument,
  documents,
  pending,
  mergeSnapshot,
  preference,
  setPreference,
  userDb,
  importGuest,
  disableDeckWrites,
} from "../src/storage-engine";
import type { SyncResponse, Deck } from "../src/types";
let db: DatabaseSync;
beforeEach(() => {
  db = new DatabaseSync(":memory:");
  const adapter: any = {
    execAsync: async (sql: string) => {
      db.exec(sql);
    },
    runAsync: async (sql: string, ...args: any[]) => {
      const r = db.prepare(sql).run(...args);
      return { changes: r.changes, lastInsertRowId: Number(r.lastInsertRowid) };
    },
    getFirstAsync: async (sql: string, ...args: any[]) =>
      db.prepare(sql).get(...args) || null,
    getAllAsync: async (sql: string, ...args: any[]) =>
      db.prepare(sql).all(...args),
    withExclusiveTransactionAsync: async (fn: (tx: any) => Promise<any>) => {
      db.exec("BEGIN");
      try {
        await fn(adapter);
        db.exec("COMMIT");
      } catch (e) {
        db.exec("ROLLBACK");
        throw e;
      }
    },
  };
  configureStorage(async () => adapter, randomUUID);
});
afterEach(() => db.close());
const snapshot = (
  amount: number,
  results: SyncResponse["results"] = [],
): SyncResponse => ({
  user: { id: 1, username: "u" },
  decks: [],
  collection: [{ card_id: 2, amount }],
  results,
});
test("an acknowledgement cannot overwrite an edit made during a network request", async () => {
  await saveDocument("user:1", "collection", "2", { card_id: 2, amount: 3 });
  const sent = await pending("user:1");
  await saveDocument("user:1", "collection", "2", { card_id: 2, amount: 9 });
  await mergeSnapshot(
    "user:1",
    snapshot(3, [{ operation_id: sent[0]!.operation.operation_id, ok: true }]),
    sent,
  );
  assert.equal((await documents<any>("user:1", "collection"))[0].amount, 9);
  assert.equal((await pending("user:1")).length, 1);
  const final = await pending("user:1");
  await mergeSnapshot(
    "user:1",
    snapshot(9, [{ operation_id: final[0]!.operation.operation_id, ok: true }]),
    final,
  );
  assert.equal((await pending("user:1")).length, 0);
  await mergeSnapshot("user:1", snapshot(12), []);
  assert.equal((await documents<any>("user:1", "collection"))[0].amount, 12);
});
test("failed immutable operations stay local and are replaced by a fresh edit", async () => {
  await saveDocument("user:1", "collection", "2", { card_id: 2, amount: 4 });
  const sent = await pending("user:1");
  await mergeSnapshot(
    "user:1",
    snapshot(1, [
      {
        operation_id: sent[0]!.operation.operation_id,
        ok: false,
        error: "missing item",
      },
    ]),
    sent,
  );
  assert.equal((await pending("user:1")).length, 0);
  assert.equal((await documents<any>("user:1", "collection"))[0].amount, 4);
  assert.ok((await documents<any>("user:1", "collection"))[0].sync_error);
  await saveDocument("user:1", "collection", "2", { card_id: 2, amount: 5 });
  assert.equal((await pending("user:1")).length, 1);
});
test("guest and account queues are isolated and user data survives catalog pointer changes", async () => {
  await saveDocument("guest", "collection", "2", { card_id: 2, amount: 2 });
  await saveDocument("user:1", "collection", "2", { card_id: 2, amount: 7 });
  await saveDocument("user:2", "collection", "2", { card_id: 2, amount: 1 });
  assert.equal((await pending("guest")).length, 0);
  assert.equal((await pending("user:1")).length, 1);
  assert.equal((await documents<any>("user:2", "collection"))[0].amount, 1);
  await setPreference("catalog-active", "new.sqlite");
  assert.equal(await preference("catalog-active", ""), "new.sqlite");
  assert.equal((await documents<any>("guest", "collection"))[0].amount, 2);
});
test("guest import copies selected quantities without creating decks", async () => {
  const deck: Deck = {
    uuid: randomUUID(),
    name: "draft",
    character_id: 1,
    description: "",
    keyword: "",
    tags: "",
    visibility: "private",
    cards: [],
  };
  await saveDocument("guest", "deck", deck.uuid, deck, false);
  await saveDocument("guest", "collection", "2", { card_id: 2, amount: 5 });
  await saveDocument("guest", "collection", "3", { card_id: 3, amount: 8 });
  await importGuest("user:1", [2]);
  const imported = await documents<Deck>("user:1", "deck");
  assert.equal(imported.length, 0);
  assert.equal((await documents<any>("user:1", "collection")).length, 1);
  assert.equal((await documents<any>("user:1", "collection"))[0].amount, 5);
});

test("read-only upgrade archives old deck edits and keeps collection synchronization", async () => {
  await saveDocument("user:1", "deck", "draft", {
    uuid: "draft",
    name: "pending draft",
  });
  await saveDocument(
    "user:2",
    "deck",
    "delete",
    { uuid: "delete", deleted: true },
    true,
    "delete",
  );
  await saveDocument(
    "guest",
    "deck",
    "guest",
    { uuid: "guest", name: "guest draft" },
    false,
  );
  await saveDocument("user:1", "collection", "2", { card_id: 2, amount: 5 });
  await disableDeckWrites();
  await disableDeckWrites();
  assert.equal((await pending("user:1")).length, 1);
  assert.equal((await pending("user:1"))[0]!.operation.entity, "collection");
  assert.equal((await pending("user:2")).length, 0);
  assert.equal((await documents("user:1", "deck")).length, 0);
  assert.equal(
    (await documents<any>("user:1", "legacy_deck"))[0].name,
    "pending draft",
  );
  assert.equal(
    (await documents<any>("guest", "legacy_deck"))[0].name,
    "guest draft",
  );
  const response = snapshot(5);
  response.decks = [{ uuid: "draft", id: 1, name: "web version" } as Deck];
  await mergeSnapshot("user:1", response, []);
  assert.equal(
    (await documents<Deck>("user:1", "deck"))[0]!.name,
    "web version",
  );
});
