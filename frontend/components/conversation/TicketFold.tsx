import Link from "next/link";

import { StopTicketButton } from "@/components/conversation/StopTicketButton";
import type { TicketReports } from "@/components/conversation/ticketReports";
import type { TicketWork } from "@/components/conversation/ticketWork";

const HEADING = "mb-1 text-xs font-medium text-ink-soft";

/** What a ticket's line opens to: what it asked and was told, its steps, its full log and a stop. */
export function TicketFold({
  ticketId,
  reports,
  work,
  stoppable,
}: {
  ticketId: string;
  reports: TicketReports;
  work: TicketWork;
  stoppable: boolean;
}) {
  return (
    <div className="space-y-3 py-1">
      {reports.questions.map((question, index) => (
        <div key={index} className="text-sm">
          <p className={HEADING}>Asked you</p>
          <p className="break-words">{question}</p>
          {work.answers[index] !== undefined && (
            <p className="mt-1 break-words text-ink-soft">You said: {work.answers[index]}</p>
          )}
        </div>
      ))}
      {work.steps.length > 0 && (
        <div>
          <p className={HEADING}>Steps</p>
          <ol className="space-y-0.5 text-xs text-ink-soft">
            {work.steps.map((step, index) => (
              <li key={index} className="flex gap-2">
                <span className="w-4 shrink-0 tabular-nums">{index + 1}</span>
                <span className="min-w-0 break-words text-ink">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
      <div className="flex items-center gap-4">
        <Link
          href={`/t/${encodeURIComponent(ticketId)}`}
          className="inline-block text-xs text-accent hover:text-ink"
        >
          Full log
        </Link>
        {stoppable && <StopTicketButton ticketId={ticketId} />}
      </div>
    </div>
  );
}
