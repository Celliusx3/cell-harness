import { z } from "zod";

import { parsedResult, PREVIEW_URI, SERVER } from "@/components/computer/server";
import { callAppTool } from "@/lib/api";

const MIB = 1024 * 1024;
const UPLOAD_LIMIT_BYTES = 10 * MIB;
const IMAGE_TYPES: Record<string, string> = {
  gif: "image/gif",
  jpeg: "image/jpeg",
  jpg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
};

const FileEntry = z.object({
  path: z.string(),
  kind: z.enum(["file", "dir"]),
  size: z.number().int().nonnegative(),
});
export type FileEntry = z.infer<typeof FileEntry>;

const Listed = z.object({
  structuredContent: z.object({ path: z.string(), entries: z.array(FileEntry) }),
});
const FileText = z.object({ structuredContent: z.object({ path: z.string(), content: z.string() }) });
const Downloaded = z.object({
  structuredContent: z.object({ path: z.string(), content_base64: z.base64() }),
});
const Uploaded = z.object({
  structuredContent: z.object({ path: z.string(), size: z.number().int().nonnegative() }),
});

interface Crumb {
  name: string;
  path: string;
}

export function baseName(path: string): string {
  return path.slice(path.lastIndexOf("/") + 1);
}

export function imageType(path: string): string | undefined {
  const name = baseName(path);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? IMAGE_TYPES[name.slice(dot + 1).toLowerCase()] : undefined;
}

export function crumbs(path: string): Crumb[] {
  const names = path ? path.split("/") : [];
  return [
    { name: "~", path: "" },
    ...names.map((name, at) => ({ name, path: names.slice(0, at + 1).join("/") })),
  ];
}

export function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < MIB) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / MIB).toFixed(1)} MiB`;
}

function bytesOf(base64: string): Uint8Array<ArrayBuffer> {
  const binary = atob(base64);
  const bytes = new Uint8Array(new ArrayBuffer(binary.length));
  for (let at = 0; at < binary.length; at += 1) bytes[at] = binary.charCodeAt(at);
  return bytes;
}

function base64Of(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const url = reader.result;
      if (typeof url === "string") resolve(url.slice(url.indexOf(",") + 1));
      else reject(new Error(`${file.name} could not be read.`));
    };
    reader.onerror = () => reject(reader.error ?? new Error(`${file.name} could not be read.`));
    reader.readAsDataURL(file);
  });
}

export async function listFolder(path: string): Promise<FileEntry[]> {
  const result = await callAppTool(SERVER, "file_list", { path }, PREVIEW_URI);
  return parsedResult(Listed, result).structuredContent.entries;
}

/** A text file's content, refused past 2 MiB or when it is not UTF-8. */
export async function readText(path: string): Promise<string> {
  const result = await callAppTool(SERVER, "file_read", { path }, PREVIEW_URI);
  return parsedResult(FileText, result).structuredContent.content;
}

/** A file's bytes, refused past 10 MiB. */
export async function downloadBytes(path: string): Promise<Uint8Array<ArrayBuffer>> {
  const result = await callAppTool(SERVER, "file_download", { path }, PREVIEW_URI);
  return bytesOf(parsedResult(Downloaded, result).structuredContent.content_base64);
}

/** Every file into `folder`, one at a time; none is sent when any is past 10 MiB. */
export async function uploadFiles(folder: string, files: File[]): Promise<void> {
  const tooLargeNames = files.filter((file) => file.size > UPLOAD_LIMIT_BYTES).map((file) => file.name);
  if (tooLargeNames.length > 0) {
    throw new Error(`Larger than 10 MiB, so nothing was uploaded: ${tooLargeNames.join(", ")}`);
  }
  for (const file of files) {
    const path = folder ? `${folder}/${file.name}` : file.name;
    const result = await callAppTool(
      SERVER,
      "file_upload",
      { path, content_base64: await base64Of(file) },
      PREVIEW_URI,
    );
    parsedResult(Uploaded, result);
  }
}
