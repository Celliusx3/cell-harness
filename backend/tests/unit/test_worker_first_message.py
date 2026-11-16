"""Workers share one system text; the title, and any skill the task names, open the turn."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from harness.llm import SystemMessage
from harness.session.repository.jsonl_session_repository import JsonlSessionRepository
from harness.session.service.session_service import SessionService
from harness.skills import SkillService
from harness.skills.service.prompt import instructions
from harness.tickets.domain.models import Ticket
from harness.tickets.domain.named_skills import named_skills
from harness.tickets.domain.prompts import WORKER_INTRO
from harness.tickets.service.worker import RuntimeTicketWorker, worker_session_id
from tests.unit.fakes import SteppedClient, completed
from tests.unit.helpers import runtime_over, skills_at


def ticket(ticket_id: str, title: str, task: str) -> Ticket:
    return Ticket(
        id=ticket_id,
        bot_id="b",
        title=title,
        task=task,
        state="working",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def write_skill(root: Path, name: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(
        f"---\ndescription: {name} things.\n---\nDo {name} page by page.\n"
    )


def worker_over(
    tmp_path: Path, skills: SkillService
) -> tuple[RuntimeTicketWorker, SteppedClient, SessionService]:
    client = SteppedClient(completed("Done."))
    sessions = SessionService(JsonlSessionRepository(tmp_path / "workers"))
    runtime = runtime_over(client, guidance="BASE")
    return RuntimeTicketWorker(runtime, sessions, lambda _bot_id: 3, skills), client, sessions


async def first_message(sessions: SessionService, ticket_id: str) -> str:
    stored = await sessions.read(worker_session_id(ticket_id))
    return next(e.message.content for e in stored.events() if e.type == "user/message")


def test_the_intro_names_no_ticket() -> None:
    assert "{" not in WORKER_INTRO
    assert "titled" not in WORKER_INTRO


async def test_sibling_workers_share_one_system_text_and_each_hears_its_title(
    tmp_path: Path,
) -> None:
    each, client, sessions = worker_over(tmp_path, skills_at(tmp_path / "skills"))

    await each.start(ticket("t1", "Part 1", "Translate pages 1-8."), mode="auto")
    await each.start(ticket("t2", "Part 2", "Translate pages 9-16."), mode="auto")

    systems = [
        m.content for call in client.seen_per_call for m in call if isinstance(m, SystemMessage)
    ]
    assert len(systems) == 2 and systems[0] == systems[1]
    assert systems[0].startswith(WORKER_INTRO)
    assert (await first_message(sessions, "t1")).startswith(
        "Your ticket: Part 1\n\nTranslate pages 1-8."
    )
    assert (await first_message(sessions, "t2")).startswith("Your ticket: Part 2\n\n")


async def test_a_task_that_names_a_skill_starts_with_that_skill_loaded(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "comic-translator")
    write_skill(root, "pdf")
    skills = skills_at(root)
    each, _client, sessions = worker_over(tmp_path, skills)

    await each.start(
        ticket("t1", "Part 1", "Translate pages 1-8 with the comic-translator skill."), mode="auto"
    )

    message = await first_message(sessions, "t1")
    assert message.endswith("\n\n" + instructions(skills.find("comic-translator")))
    assert "Do comic-translator page by page." in message
    assert "Do pdf" not in message


async def test_a_task_that_names_an_unknown_skill_gets_no_skill_text(tmp_path: Path) -> None:
    root = tmp_path / "skills"
    write_skill(root, "comic-translator")
    each, _client, sessions = worker_over(tmp_path, skills_at(root))

    await each.start(ticket("t1", "Part 1", "Use the manga-cleaner skill."), mode="auto")

    message = await first_message(sessions, "t1")
    assert '<skill name="' not in message
    assert message == "Your ticket: Part 1\n\nUse the manga-cleaner skill.\n\n" + (
        "Your bot can run 3 workers at once."
    )


def test_a_skill_is_named_only_as_written_before_the_word_skill() -> None:
    names = ("comic-translator", "translator", "pdf")

    assert named_skills("Use the comic-translator skill.", names) == ("comic-translator",)
    assert named_skills("Use the translator skills folder.", names) == ()
    assert named_skills("Use the pdf skill and the translator skill", names) == (
        "translator",
        "pdf",
    )
    assert named_skills("Translate with comic-translator.", names) == ()
