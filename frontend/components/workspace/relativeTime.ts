const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

/** How long before `now` the time `then` was, as "just now", "4 min ago", "2 h ago" or "3 days ago". */
export function timeAgo(then: Date, now: Date): string {
  const past = now.getTime() - then.getTime();
  if (past < MINUTE_MS) return "just now";
  if (past < HOUR_MS) return `${Math.floor(past / MINUTE_MS)} min ago`;
  if (past < DAY_MS) return `${Math.floor(past / HOUR_MS)} h ago`;
  const days = Math.floor(past / DAY_MS);
  return days === 1 ? "1 day ago" : `${days} days ago`;
}
