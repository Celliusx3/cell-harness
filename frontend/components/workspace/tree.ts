import { childPath, isWithin, type WorkspaceEntry } from "@/components/workspace/workspace";

/** The folders of a workspace listed so far, which are open, and which files appeared since. */
export interface Tree {
  listings: ReadonlyMap<string, WorkspaceEntry[]>;
  expanded: ReadonlySet<string>;
  fresh: ReadonlySet<string>;
}

export const EMPTY_TREE: Tree = { listings: new Map(), expanded: new Set([""]), fresh: new Set() };

/** The paths of files in `next` that `previous` did not list; none on a folder's first listing. */
function appearedFiles(folder: string, previous: WorkspaceEntry[] | undefined, next: WorkspaceEntry[]): string[] {
  if (previous === undefined) return [];
  const known = new Set(previous.map((entry) => entry.name));
  return next
    .filter((entry) => entry.kind === "file" && !known.has(entry.name))
    .map((entry) => childPath(folder, entry.name));
}

/** `tree` with `folder` listed as `entries`, each file new to it marked fresh. */
export function withListing(tree: Tree, folder: string, entries: WorkspaceEntry[]): Tree {
  const appeared = appearedFiles(folder, tree.listings.get(folder), entries);
  return {
    ...tree,
    listings: new Map(tree.listings).set(folder, entries),
    fresh: new Set([...tree.fresh, ...appeared]),
  };
}

/** `tree` with `folder` opened when it was closed, or closed when it was open. */
export function toggledFolder(tree: Tree, folder: string): Tree {
  const expanded = new Set(tree.expanded);
  if (!expanded.delete(folder)) expanded.add(folder);
  return { ...tree, expanded };
}

/** `tree` with `path` no longer marked fresh. */
export function seenFile(tree: Tree, path: string): Tree {
  const fresh = new Set(tree.fresh);
  fresh.delete(path);
  return { ...tree, fresh };
}

/** `tree` with nothing kept at `path` or inside it. */
export function withoutPath(tree: Tree, path: string): Tree {
  const kept = (each: string) => !isWithin(each, path);
  return {
    listings: new Map([...tree.listings].filter(([folder]) => kept(folder))),
    expanded: new Set([...tree.expanded].filter(kept)),
    fresh: new Set([...tree.fresh].filter(kept)),
  };
}

/** The entry `name` of `folder`, when that folder is listed and holds it. */
export function entryAt(tree: Tree, folder: string, name: string): WorkspaceEntry | undefined {
  return tree.listings.get(folder)?.find((entry) => entry.name === name);
}
