/** The text of a thrown value, for a dialog or the setup form's error line. */
export function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
