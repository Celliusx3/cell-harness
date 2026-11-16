import type { Bot, Group } from "@/lib/types";

export interface WorkspaceChoice {
  chatId: string;
  name: string;
}

/** The group's own workspace, then each active member's, in member order; a member's chat id is its bot id. */
export function workspaceChoices(group: Group, activeBots: Bot[]): WorkspaceChoice[] {
  const nameOf = new Map(activeBots.map((bot) => [bot.id, bot.name]));
  const members = group.member_ids.flatMap((id) => {
    const name = nameOf.get(id);
    return name === undefined ? [] : [{ chatId: id, name }];
  });
  return [{ chatId: group.id, name: group.name }, ...members];
}
