import { Field, INPUT_CLASSES } from "@/components/credentials/CredentialFields";
import type { FieldErrors, ServerField, ServerForm, SettingRow } from "@/lib/mcpServerForm";

const ROW_BUTTON =
  "shrink-0 rounded-md border border-line bg-surface px-2 py-0.5 text-xs text-ink-soft transition hover:bg-line hover:text-ink";

interface ServerFieldsProps {
  form: ServerForm;
  isEditing: boolean;
  errors: FieldErrors;
  onChange: (form: ServerForm) => void;
}

/** Name (for a new server), command, arguments one per line, plain settings, and the keys it needs; each with its errors. */
export function ServerFields({ form, isEditing, errors, onChange }: ServerFieldsProps) {
  const change = (update: Partial<ServerForm>) => onChange({ ...form, ...update });
  return (
    <div className="grid gap-3">
      {!isEditing && (
        <Field label="Name" htmlFor="server-name">
          <input
            id="server-name"
            value={form.name}
            onChange={(event) => change({ name: event.target.value })}
            placeholder="lowercase letters and digits, such as exa"
            autoComplete="off"
            className={`font-mono ${INPUT_CLASSES}`}
          />
          <Errors errors={errors} field="name" />
        </Field>
      )}
      <Field label="Command" htmlFor="server-command">
        <input
          id="server-command"
          value={form.command}
          onChange={(event) => change({ command: event.target.value })}
          placeholder="npx"
          autoComplete="off"
          className={`font-mono ${INPUT_CLASSES}`}
        />
        <Errors errors={errors} field="command" />
      </Field>
      <Field label="Arguments" htmlFor="server-arguments">
        <textarea
          id="server-arguments"
          value={form.argumentLines}
          onChange={(event) => change({ argumentLines: event.target.value })}
          placeholder={"One per line, such as\n-y\nexa-mcp-server"}
          rows={3}
          className={`font-mono ${INPUT_CLASSES}`}
        />
        <Errors errors={errors} field="argumentLines" />
      </Field>
      <SettingRows rows={form.settings} errors={errors} onChange={(settings) => change({ settings })} />
      <NeedRows names={form.needs} errors={errors} onChange={(needs) => change({ needs })} />
    </div>
  );
}

interface SettingRowsProps {
  rows: SettingRow[];
  errors: FieldErrors;
  onChange: (rows: SettingRow[]) => void;
}

function SettingRows({ rows, errors, onChange }: SettingRowsProps) {
  const changeRow = (index: number, update: Partial<SettingRow>) =>
    onChange(rows.map((row, at) => (at === index ? { ...row, ...update } : row)));
  return (
    <fieldset className="flex min-w-0 flex-col gap-1.5">
      <legend className="pb-1.5 text-xs text-ink-soft">Settings</legend>
      {rows.map((row, index) => (
        <div key={index} className="flex items-center gap-2">
          <input
            aria-label={`Setting ${index + 1} name`}
            value={row.name}
            onChange={(event) => changeRow(index, { name: event.target.value })}
            placeholder="NAME"
            autoComplete="off"
            className={`min-w-0 flex-1 font-mono ${INPUT_CLASSES}`}
          />
          <input
            aria-label={`Setting ${index + 1} value`}
            value={row.value}
            onChange={(event) => changeRow(index, { value: event.target.value })}
            placeholder="value"
            autoComplete="off"
            className={`min-w-0 flex-1 font-mono ${INPUT_CLASSES}`}
          />
          <RemoveRow label={`Remove setting ${index + 1}`} onClick={() => onChange(rows.filter((_, at) => at !== index))} />
        </div>
      ))}
      <AddRow label="Add setting" onClick={() => onChange([...rows, { name: "", value: "" }])} />
      <p className="text-xs text-ink-soft">Plain settings only; a key goes on Credentials.</p>
      <Errors errors={errors} field="settings" />
    </fieldset>
  );
}

interface NeedRowsProps {
  names: string[];
  errors: FieldErrors;
  onChange: (names: string[]) => void;
}

function NeedRows({ names, errors, onChange }: NeedRowsProps) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-1.5">
      <legend className="pb-1.5 text-xs text-ink-soft">Keys it needs</legend>
      {names.map((name, index) => (
        <div key={index} className="flex items-center gap-2">
          <input
            aria-label={`Key ${index + 1} name`}
            value={name}
            onChange={(event) => onChange(names.map((held, at) => (at === index ? event.target.value : held)))}
            placeholder="EXA_API_KEY"
            autoComplete="off"
            className={`min-w-0 flex-1 font-mono ${INPUT_CLASSES}`}
          />
          <RemoveRow label={`Remove key ${index + 1}`} onClick={() => onChange(names.filter((_, at) => at !== index))} />
        </div>
      ))}
      <AddRow label="Add key" onClick={() => onChange([...names, ""])} />
      <p className="text-xs text-ink-soft">Only the names: add each key&apos;s value on Credentials as a Capability key.</p>
      <Errors errors={errors} field="needs" />
    </fieldset>
  );
}

function AddRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`self-start ${ROW_BUTTON}`}>
      {label}
    </button>
  );
}

function RemoveRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} aria-label={label} className={ROW_BUTTON}>
      Remove
    </button>
  );
}

/** The errors under `field`, in the words they came in. */
export function Errors({ errors, field }: { errors: FieldErrors; field: ServerField }) {
  const shown = errors[field] ?? [];
  if (shown.length === 0) return null;
  return (
    <ul className="space-y-0.5 text-xs break-words text-danger">
      {shown.map((message) => (
        <li key={message}>{message}</li>
      ))}
    </ul>
  );
}
