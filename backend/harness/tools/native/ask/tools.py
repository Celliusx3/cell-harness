"""`ask_model` and `ask_model_jobs`, as the model is offered them."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path

from harness.files import ChatFileService
from harness.images import ImageService
from harness.llm import Usage
from harness.runtime.models import BotModels, ModelChoice
from harness.tools.domain.context import ToolContext
from harness.tools.domain.outcome import EXECUTION_ERROR, INVALID_ARGUMENTS, Failure, Ok
from harness.tools.domain.tool import Tool
from harness.tools.native.ask import _descriptions
from harness.tools.native.ask._answer import parsed_reply
from harness.tools.native.ask._call import (
    ModelReply,
    UnsendableFile,
    answer_target,
    model_of,
    model_reply,
    question_of,
    save_answer,
)
from harness.tools.native.ask._jobs import jobs_in
from harness.tools.native.ask.models import (
    AskModelArgs,
    AskModelJobsArgs,
    JobFailure,
    JobsAnswered,
    ModelAnswer,
    ModelJob,
)
from harness.tools.native.files import UnviewableImage, paths_in_chat

ASK_MODEL = "ask_model"
ASK_MODEL_JOBS = "ask_model_jobs"


def ask_model_tool(
    files: ChatFileService, images: ImageService, models: BotModels
) -> Tool[AskModelArgs]:
    """The tool that asks the calling bot's model one question about files of this chat's."""

    async def execute(args: AskModelArgs, context: ToolContext) -> Ok | Failure:
        choice = await model_of(models, context.origin.bot_id)
        if isinstance(choice, Failure):
            return choice
        return await _asked(files, images, choice, args, context)

    return Tool.from_model(
        name=ASK_MODEL,
        description=_descriptions.ASK_MODEL,
        args_model=AskModelArgs,
        execute=execute,
    )


def ask_model_jobs_tool(
    files: ChatFileService, images: ImageService, models: BotModels, *, at_once: int
) -> Tool[AskModelJobsArgs]:
    """The tool that makes every `ask_model` call a jobs file in this chat lists,
    `at_once` of them at a time."""

    async def execute(args: AskModelJobsArgs, context: ToolContext) -> Ok | Failure:
        found = paths_in_chat(files, context.origin.conversation_id, [args.jobs_path])
        if isinstance(found, Failure):
            return found
        jobs = await asyncio.to_thread(jobs_in, found[0])
        if isinstance(jobs, Failure):
            return jobs
        choice = await model_of(models, context.origin.bot_id)
        if isinstance(choice, Failure):
            return choice
        gate = asyncio.Semaphore(at_once)

        async def one(job: ModelJob) -> Ok | Failure:
            async with gate:
                return await _asked(files, images, choice, job, context)

        outcomes = await asyncio.gather(*(one(job) for job in jobs))
        done = _jobs_answered(jobs, outcomes)
        return Ok(done.model_dump_json(), data=done.model_dump())

    return Tool.from_model(
        name=ASK_MODEL_JOBS,
        description=_descriptions.ASK_MODEL_JOBS,
        args_model=AskModelJobsArgs,
        execute=execute,
    )


def _jobs_answered(jobs: Sequence[ModelJob], outcomes: Sequence[Ok | Failure]) -> JobsAnswered:
    """How `jobs` went: each that failed, by its save_to, and the tokens of those answered."""
    failed = [
        JobFailure(save_to=job.save_to, error=outcome.message)
        for job, outcome in zip(jobs, outcomes, strict=True)
        if isinstance(outcome, Failure)
    ]
    usages = [
        ModelAnswer.model_validate(outcome.data).usage
        for outcome in outcomes
        if isinstance(outcome, Ok)
    ]
    return JobsAnswered(answered=len(jobs) - len(failed), failed=failed, usage=_usage_total(usages))


def _usage_total(usages: Sequence[Usage | None]) -> Usage:
    """The tokens of every call that reported them, added up."""
    reported = [usage for usage in usages if usage is not None]
    return Usage(
        input_tokens=sum(usage.input_tokens for usage in reported),
        output_tokens=sum(usage.output_tokens for usage in reported),
        cached_input_tokens=sum(usage.cached_input_tokens or 0 for usage in reported),
    )


async def _asked(
    files: ChatFileService,
    images: ImageService,
    choice: ModelChoice,
    args: AskModelArgs,
    context: ToolContext,
) -> Ok | Failure:
    """`args` asked of `choice`, its reply saved when `args` says where."""
    chat_id = context.origin.conversation_id
    found = paths_in_chat(files, chat_id, args.paths)
    if isinstance(found, Failure):
        return found
    target = None if args.save_to is None else answer_target(files.workspace(chat_id), args.save_to)
    if isinstance(target, Failure):
        return target
    try:
        question = await asyncio.to_thread(question_of, images, args.instructions, found)
    except (UnviewableImage, UnsendableFile) as err:
        return Failure(INVALID_ARGUMENTS, str(err))
    if isinstance(question, Failure):
        return question
    reply = await model_reply(choice, question)
    if isinstance(reply, Failure):
        return reply
    return await _answered(reply, target)


async def _answered(reply: ModelReply, target: Path | None) -> Ok | Failure:
    """`reply` as the model and a script receive it, once written to `target` when there is one."""
    parsed = parsed_reply(reply.text)
    if target is not None:
        try:
            await asyncio.to_thread(save_answer, target, parsed.text)
        except OSError as err:
            return Failure(EXECUTION_ERROR, f"the reply could not be saved to {target}: {err}")
    saved_to = None if target is None else str(target)
    answer = ModelAnswer(answer=parsed.value, saved_to=saved_to, usage=reply.usage)
    text = parsed.text if target is None else f"{parsed.text}\n\nSaved to {target}"
    return Ok(text, data=answer.model_dump())
