import { MarkdownBody } from "@/components/conversation/Message";
import type { TicketResultItem } from "@/components/conversation/timelineItems";

/** A ticket's ready result, whole, as the bot's own message; its ticket's line already folded above. */
export function TicketResult({ item }: { item: TicketResultItem }) {
  return <MarkdownBody content={item.text} streaming={false} />;
}
