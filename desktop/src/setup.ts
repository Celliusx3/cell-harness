import { randomBytes } from "node:crypto";
import { closeSync, fsyncSync, mkdirSync, openSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";

import { messageOf } from "./errors";

export type LocalSettings = Readonly<Record<string, unknown>>;

export interface Endpoint {
  readonly baseUrl: string;
  readonly model: string;
}

export interface Answers extends Endpoint {
  readonly apiKey: string;
}

const ENCRYPTION_KEY_BYTES = 32;
const TEMP_SUFFIX_BYTES = 6;
const OWNER_ONLY = 0o600;
const WEB_PROTOCOLS: ReadonlySet<string> = new Set(["http:", "https:"]);
const COMMITTED_CONFIG = "desktop/config.json";
const API_KEY_REFUSAL = "Paste your API key.";
const ENDPOINT_REFUSAL = "The endpoint must be an http:// or https:// address.";
const MODEL_REFUSAL = "Type the model's name.";

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

/** Whether the setup window must ask for an API key first. */
export function needsSetup(settings: LocalSettings | null): boolean {
  return settings === null || !isFilled(sectionOf(settings, "llm").api_key);
}

/** What the form shows first: the file's endpoint and model, else the app's own. */
export function formDefaults(settings: LocalSettings | null, committed: Endpoint): Endpoint {
  const llm = sectionOf(settings, "llm");
  return {
    baseUrl: typeof llm.base_url === "string" ? llm.base_url : committed.baseUrl,
    model: typeof llm.model === "string" ? llm.model : committed.model,
  };
}

/** The form's answers, trimmed; a blank key or model, or an endpoint that is not a web address, is refused. */
export function checkAnswers(raw: unknown): Answers {
  if (!isJsonObject(raw)) throw new Error(API_KEY_REFUSAL);
  const answers = { apiKey: trimmed(raw.apiKey), baseUrl: trimmed(raw.baseUrl), model: trimmed(raw.model) };
  if (answers.apiKey === "") throw new Error(API_KEY_REFUSAL);
  if (!isWebAddress(answers.baseUrl)) throw new Error(ENDPOINT_REFUSAL);
  if (answers.model === "") throw new Error(MODEL_REFUSAL);
  return answers;
}

/** The settings with the answers saved and an encryption key made if there is none; every other value is kept. */
export function withSetup(
  settings: LocalSettings | null,
  answers: Answers,
  committed: Endpoint,
  newEncryptionKey: () => string,
): LocalSettings {
  return {
    ...settings,
    llm: llmWithAnswers(sectionOf(settings, "llm"), answers, committed),
    secrets: secretsWithKey(sectionOf(settings, "secrets"), newEncryptionKey),
  };
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

/** The endpoint and model the app ships with, from the text of its committed settings. */
export function committedEndpoint(configJson: string): Endpoint {
  const parsed: unknown = JSON.parse(configJson);
  const llm = isJsonObject(parsed) ? sectionOf(parsed, "llm") : {};
  return { baseUrl: committedString(llm.base_url, "llm.base_url"), model: committedString(llm.model, "llm.model") };
}

/** A new key for the harness's saved secrets: 32 random bytes as hex. */
export function newEncryptionKey(): string {
  return randomBytes(ENCRYPTION_KEY_BYTES).toString("hex");
}

function llmWithAnswers(llm: LocalSettings, answers: Answers, committed: Endpoint): LocalSettings {
  const { base_url: _baseUrl, model: _model, ...kept } = llm;
  return {
    ...kept,
    api_key: answers.apiKey,
    ...(answers.baseUrl === committed.baseUrl ? {} : { base_url: answers.baseUrl }),
    ...(answers.model === committed.model ? {} : { model: answers.model }),
  };
}

function secretsWithKey(secrets: LocalSettings, newEncryptionKey: () => string): LocalSettings {
  return isFilled(secrets.encryption_key) ? secrets : { ...secrets, encryption_key: newEncryptionKey() };
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

function committedString(value: unknown, key: string): string {
  if (typeof value !== "string") throw new Error(`${COMMITTED_CONFIG} has no ${key}`);
  return value;
}

function isJsonObject(value: unknown): value is LocalSettings {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFilled(value: unknown): boolean {
  return typeof value === "string" && value.trim() !== "";
}

function isWebAddress(text: string): boolean {
  return URL.canParse(text) && WEB_PROTOCOLS.has(new URL(text).protocol);
}

function isNoSuchFile(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}

function trimmed(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
