import { randomBytes } from "node:crypto";
import { closeSync, fsyncSync, mkdirSync, openSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

import { messageOf } from "./errors";

export type LocalSettings = Readonly<Record<string, unknown>>;

const ENCRYPTION_KEY_BYTES = 32;
const TEMP_SUFFIX_BYTES = 6;
const OWNER_ONLY = 0o600;

/** The friend's settings file, refused when it is not a JSON object. */
export function parseLocalSettings(text: string, file: string): LocalSettings {
  const parsed = parseJson(text, file);
  if (!isJsonObject(parsed)) throw new Error(`${file} does not hold a JSON object`);
  return parsed;
}

/** The friend's settings file, or null when there is none yet. */
export function readLocalSettings(file: string): LocalSettings | null {
  const text = readTextIfPresent(file);
  return text === null ? null : parseLocalSettings(text, file);
}

/** The settings with a new encryption key when they hold none or a blank one, every other value kept; a filled key returns the same settings. */
export function withEncryptionKey(settings: LocalSettings | null, newEncryptionKey: () => string): LocalSettings {
  const secrets = sectionOf(settings, "secrets");
  if (settings !== null && isFilled(secrets.encryption_key)) return settings;
  return { ...settings, secrets: { ...secrets, encryption_key: newEncryptionKey() } };
}

/** Replaces the file in one rename, so a crash never leaves half of it; only its owner can read it. */
export function writeLocalSettings(file: string, settings: LocalSettings): void {
  mkdirSync(path.dirname(file), { recursive: true });
  const temp = `${file}.${randomBytes(TEMP_SUFFIX_BYTES).toString("hex")}.tmp`;
  try {
    writeOwnerOnly(temp, `${JSON.stringify(settings, null, 2)}\n`);
    renameSync(temp, file);
  } catch (error) {
    rmSync(temp, { force: true });
    throw error;
  }
}

/** A new key for the harness's saved secrets: 32 random bytes as hex. */
export function newEncryptionKey(): string {
  return randomBytes(ENCRYPTION_KEY_BYTES).toString("hex");
}

function parseJson(text: string, file: string): unknown {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${file} is not valid JSON: ${messageOf(error)}`);
  }
}

function readTextIfPresent(file: string): string | null {
  try {
    return readFileSync(file, "utf8");
  } catch (error) {
    if (isNoSuchFile(error)) return null;
    throw error;
  }
}

function writeOwnerOnly(file: string, text: string): void {
  const descriptor = openSync(file, "wx", OWNER_ONLY);
  try {
    writeFileSync(descriptor, text);
    fsyncSync(descriptor);
  } finally {
    closeSync(descriptor);
  }
}

function sectionOf(settings: LocalSettings | null, key: string): LocalSettings {
  const value = settings?.[key];
  return isJsonObject(value) ? value : {};
}

function isJsonObject(value: unknown): value is LocalSettings {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFilled(value: unknown): boolean {
  return typeof value === "string" && value.trim() !== "";
}

function isNoSuchFile(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}
