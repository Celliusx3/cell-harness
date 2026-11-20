/** The group wire types, mirroring `backend/harness/groups/domain/models.py`. */

/** Who answers a message that names no member: every member, the lead, nobody, or Auto's pick. */
export type ReplySetting = "everyone" | "lead" | "mentions" | "auto";

/** Two to six bots sharing one chat, whose id is the group's; they take turns in member order. */
export interface Group {
  id: string;
  name: string;
  member_ids: string[];
  lead_id: string | null;
  reply: ReplySetting;
  auto_model: string | null;
}

export type GroupDraft = Pick<Group, "name" | "member_ids">;
export type GroupEdit = Pick<Group, "name" | "member_ids" | "lead_id" | "reply" | "auto_model">;

/** How a goal run ended. */
export type GoalStatus = "done" | "needs_you" | "blocked" | "limit_reached" | "stopped" | "failed";
