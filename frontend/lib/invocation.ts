/** The short form of a `/name` message. */

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
