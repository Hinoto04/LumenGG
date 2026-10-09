import * as SQLite from "expo-sqlite";
import * as Crypto from "expo-crypto";
import { configureStorage } from "./storage-engine";
configureStorage(
  () => SQLite.openDatabaseAsync("lumendb-user.sqlite"),
  () => Crypto.randomUUID(),
);
export * from "./storage-engine";
