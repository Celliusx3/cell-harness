/**
 * The short form of a `/name` message.
 *
 * The backend expands `/find-place https://…` in place: what was typed, then
 * the skill in a `<skill name="…">` tag. That whole string is the logged
 * message and the one the model sees, so there is no second field to read —
 * the typed line is everything before the first marker. The order and the
 * marker are the contract, held by `backend/harness/skills/invocation.py`,
 * and a backend test pins the two literals together.
 */

export const MARKER = "\n\n<skill name=\"";

const NAME = /^[a-z0-9]+(-[a-z0-9]+)*$/;

export interface Invocation {
  skill: string;
  typed: string;
}

export function display(content: string): Invocation | null {
  const at = content.indexOf(MARKER);
  if (at < 0) return null;
  const rest = content.slice(at + MARKER.length);
  const quote = rest.indexOf('"');
  if (quote < 0) return null;
  const skill = rest.slice(0, quote);
  if (!NAME.test(skill)) return null;
  return { skill, typed: content.slice(0, at) };
}
