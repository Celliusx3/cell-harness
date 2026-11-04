import Link from "next/link";
import type { ReactNode } from "react";

import { BUILDER_ID } from "@/lib/api";
import type { Bot, Group } from "@/lib/types";

interface BotListProps {
  bots: Bot[];
  groups: Group[];
  archived: Bot[];
}

/** Every bot but Bot builder, linked to its page, then every group with its members' names, linked to its chat. */
export function BotList({ bots, groups, archived }: BotListProps) {
  const nameOf = new Map([...bots, ...archived].map((bot) => [bot.id, bot.name]));

  return (
    <>
      <BotsSection title="Bots">
        {bots
          .filter((bot) => bot.id !== BUILDER_ID)
          .map((bot) => (
            <BotsRow key={bot.id} href={`/bots/${bot.id}`} name={bot.name} detail={bot.instructions} />
          ))}
      </BotsSection>
      {groups.length > 0 && (
        <BotsSection title="Groups">
          {groups.map((group) => (
            <BotsRow
              key={group.id}
              href={`/c/${group.id}`}
              name={group.name}
              detail={group.member_ids.flatMap((id) => nameOf.get(id) ?? []).join(", ")}
            />
          ))}
        </BotsSection>
      )}
    </>
  );
}

/** One titled list on the Bots page. */
export function BotsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 text-xs font-medium text-ink-soft">{title}</h2>
      <ul className="max-w-2xl divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface-sunken">
        {children}
      </ul>
    </section>
  );
}

function BotsRow({ href, name, detail }: { href: string; name: string; detail: string }) {
  return (
    <li>
      <Link href={href} className="block px-3 py-2 transition hover:bg-line">
        <span className="block truncate text-sm font-medium">{name}</span>
        <span className="block truncate text-xs text-ink-soft">{detail}</span>
      </Link>
    </li>
  );
}
