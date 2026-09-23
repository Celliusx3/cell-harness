export type TreeNode =
  | { kind: "file"; name: string; path: string }
  | { kind: "folder"; name: string; path: string; children: TreeNode[] };

function byName(a: string, b: string): number {
  if (a < b) return -1;
  return a > b ? 1 : 0;
}

function nodesOf(paths: string[], prefix: string): TreeNode[] {
  const nested = paths.filter((path) => path.includes("/"));
  const folders = [...new Set(nested.map((path) => path.slice(0, path.indexOf("/"))))]
    .sort(byName)
    .map((name): TreeNode => {
      const head = `${name}/`;
      return {
        kind: "folder",
        name,
        path: `${prefix}${name}`,
        children: nodesOf(
          nested.filter((path) => path.startsWith(head)).map((path) => path.slice(head.length)),
          `${prefix}${head}`,
        ),
      };
    });
  const files = paths
    .filter((path) => !path.includes("/"))
    .sort(byName)
    .map((name): TreeNode => ({ kind: "file", name, path: `${prefix}${name}` }));
  return [...folders, ...files];
}

/** Flat posix paths as a tree, folders before files and each group alphabetical. */
export function fileTree(paths: string[]): TreeNode[] {
  return nodesOf(paths, "");
}
