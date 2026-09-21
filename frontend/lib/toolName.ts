/** A tool's name as a person reads it: `memory__write_note` is "write note" from the server "memory". */
export function humanise(name: string): { server: string | null; label: string } {
  const split = name.indexOf("__");
  const server = split === -1 ? null : name.slice(0, split);
  const bare = split === -1 ? name : name.slice(split + 2);
  return { server, label: bare.replace(/_/g, " ") };
}
