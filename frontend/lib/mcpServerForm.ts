import type { McpServer, McpServerChange, McpServerDraft, RefusedField } from "./mcpServers";

/** One `NAME=value` row of a server's plain settings, as typed. */
export interface SettingRow {
  name: string;
  value: string;
}

/** One key a server needs: its name, the value typed (empty keeps the saved one), and whether one is saved. */
export interface KeyRow {
  name: string;
  value: string;
  isSet: boolean;
}

/** What the server dialog's fields hold, as the person typed them. */
export interface ServerForm {
  name: string;
  command: string;
  argumentLines: string;
  settings: SettingRow[];
  needs: KeyRow[];
}

/** A dialog field an error is shown under; `form` for one that is about the whole server. */
export type ServerField = "name" | "command" | "argumentLines" | "settings" | "needs" | "form";

/** The errors to show, by the field each sits under. */
export type FieldErrors = Partial<Record<ServerField, string[]>>;

/** The request the form makes, or the errors that keep it from being sent. */
export type Built<Request> = { ok: true; request: Request } | { ok: false; errors: FieldErrors };

const FIELD_OF_REQUEST_KEY = new Map<string, ServerField>([
  ["id", "name"],
  ["command", "command"],
  ["args", "argumentLines"],
  ["env", "settings"],
  ["needs", "needs"],
  ["keys", "needs"],
]);

const PYDANTIC_VALUE_ERROR = "Value error, ";

/** The fields for a new server, or `server`'s as saved. */
export function initialServerForm(server: McpServer | null): ServerForm {
  if (server === null) return { name: "", command: "", argumentLines: "", settings: [], needs: [] };
  return {
    name: server.id,
    command: server.command,
    argumentLines: server.args.join("\n"),
    settings: Object.entries(server.env).map(([name, value]) => ({ name, value })),
    needs: server.keys.map((key) => ({ name: key.name, value: "", isSet: key.is_set })),
  };
}

/** One argument per line, as typed; a blank line is dropped. */
export function parseArgumentLines(text: string): string[] {
  return text.split(/\r?\n/).filter((line) => line.trim() !== "");
}

/** `POST /api/mcp/servers` from the form, or why it cannot be sent. */
export function serverDraft(form: ServerForm): Built<McpServerDraft> {
  const change = serverChange(form);
  return change.ok ? { ok: true, request: { id: form.name, ...change.request } } : change;
}

/** `PUT /api/mcp/servers/{id}` from the form, or why it cannot be sent. */
export function serverChange(form: ServerForm): Built<McpServerChange> {
  const settings = settingsFrom(form.settings);
  if (!settings.ok) return settings;
  const named = form.needs.map((row) => ({ ...row, name: row.name.trim() }));
  if (named.some((row) => row.name === "" && row.value !== "")) {
    return { ok: false, errors: { needs: ["Each key needs a name."] } };
  }
  const needed = named.filter((row) => row.name !== "");
  return {
    ok: true,
    request: {
      command: form.command,
      args: parseArgumentLines(form.argumentLines),
      env: settings.request,
      needs: needed.map((row) => row.name),
      keys: Object.fromEntries(needed.filter((row) => row.value !== "").map((row) => [row.name, row.value])),
    },
  };
}

/** The settings by name; a row with neither name nor value is dropped, and one with a value but no name refused. */
function settingsFrom(rows: SettingRow[]): Built<Record<string, string>> {
  const named = rows
    .map((row) => ({ name: row.name.trim(), value: row.value }))
    .filter((row) => row.name !== "" || row.value !== "");
  const errors = [
    ...(named.some((row) => row.name === "") ? ["Each setting needs a name."] : []),
    ...repeatedNames(named).map((name) => `${name} is set more than once.`),
  ];
  if (errors.length > 0) return { ok: false, errors: { settings: errors } };
  return { ok: true, request: Object.fromEntries(named.map((row) => [row.name, row.value])) };
}

function repeatedNames(rows: SettingRow[]): string[] {
  const names = rows.map((row) => row.name).filter((name) => name !== "");
  return [...new Set(names.filter((name, index) => names.indexOf(name) !== index))];
}

/** A 422's refused fields, each under the dialog field it came from, in the harness's words. */
export function fieldErrorsFrom(refused: RefusedField[]): FieldErrors {
  return refused.reduce<FieldErrors>((errors, field) => {
    const key = fieldOf(field.loc);
    return { ...errors, [key]: [...(errors[key] ?? []), withoutPrefix(field.msg)] };
  }, {});
}

function fieldOf(loc: RefusedField["loc"]): ServerField {
  const head = loc[0];
  return typeof head === "string" ? (FIELD_OF_REQUEST_KEY.get(head) ?? "form") : "form";
}

function withoutPrefix(message: string): string {
  return message.startsWith(PYDANTIC_VALUE_ERROR) ? message.slice(PYDANTIC_VALUE_ERROR.length) : message;
}
