"""The runtime the server composes: a model, the native tools, the guardrail."""

from __future__ import annotations

import dataclasses
import logging

import httpx

from harness.bots import BotService
from harness.config.settings import Settings
from harness.files import ChatFileService
from harness.images import ImageService
from harness.llm.adapters import OpenAIClient
from harness.mcp.service import McpService
from harness.prompts import CODE_PROMPT, GUIDANCE
from harness.runs.bot_messages import BotMessages
from harness.runs.service import RunService
from harness.runtime.hooks import HookChain
from harness.runtime.hooks.native.empty_reply import EmptyReplyHook
from harness.runtime.hooks.native.exact_failure import ExactFailureHook
from harness.runtime.hooks.native.no_progress import NoProgressHook
from harness.runtime.hooks.native.repeated_call import RepeatedCallHook
from harness.runtime.hooks.native.same_tool_failure import SameToolFailureHook
from harness.runtime.service import Runtime
from harness.runtime.subagents import Subagents
from harness.sandbox import DenoRunner
from harness.secrets import SecretService
from harness.session.service import SessionService
from harness.skills import SKILL, SkillService, skill_tool
from harness.tools import Approvals, ToolPipeline, ToolService
from harness.tools.client import ClientTools, ClientToolService
from harness.tools.native.bots import BOT_CREATE, MESSAGE_BOT, bot_create_tool, message_bot_tool
from harness.tools.native.clock import clock_tool
from harness.tools.native.code_mode import (
    EXECUTE_TYPESCRIPT,
    GET_FUNCTION_DETAILS,
    LIST_FUNCTIONS,
    code_mode_tools,
)
from harness.tools.native.files import (
    EXTRACT_ARCHIVE,
    MAKE_ARCHIVE,
    SEND_FILE,
    VIEW_IMAGE,
    extract_archive_tool,
    make_archive_tool,
    send_file_tool,
    view_image_tool,
)
from harness.tools.native.hand_over import HAND_OVER_TOOL
from harness.tools.native.location import GET_LOCATION_TOOL
from harness.tools.native.question import ASK_USER_TOOL
from harness.tools.native.secrets import (
    ASK_FOR_SECRET_TOOL,
    FETCH_WITH_SECRET,
    fetch_with_secret_tool,
)
from harness.tools.native.skills import (
    SKILL_DELETE,
    SKILL_SAVE,
    SKILL_WRITE_FILE,
    skill_delete_tool,
    skill_save_tool,
    skill_write_file_tool,
)
from harness.tools.native.subagent import RUN_SUBAGENT, run_subagent_tool

logger = logging.getLogger("harness.web")

CLIENT_TOOLS = ClientTools((GET_LOCATION_TOOL, ASK_USER_TOOL, ASK_FOR_SECRET_TOOL, HAND_OVER_TOOL))
SKILL_WRITES = (SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE)
DEFAULT_TOOLS = (
    LIST_FUNCTIONS,
    GET_FUNCTION_DETAILS,
    EXECUTE_TYPESCRIPT,
    SKILL,
    *SKILL_WRITES,
    BOT_CREATE,
    MESSAGE_BOT,
    RUN_SUBAGENT,
    FETCH_WITH_SECRET,
    SEND_FILE,
    EXTRACT_ARCHIVE,
    MAKE_ARCHIVE,
    VIEW_IMAGE,
    *sorted(CLIENT_TOOLS.names),
)
SUBAGENT_TOOLS = (LIST_FUNCTIONS, GET_FUNCTION_DETAILS, EXECUTE_TYPESCRIPT, SKILL)
NOT_CALLABLE_FROM_SCRIPTS = frozenset(
    {
        SKILL,
        *SKILL_WRITES,
        BOT_CREATE,
        MESSAGE_BOT,
        RUN_SUBAGENT,
        FETCH_WITH_SECRET,
        SEND_FILE,
        EXTRACT_ARCHIVE,
        MAKE_ARCHIVE,
        VIEW_IMAGE,
        *CLIENT_TOOLS.names,
    }
)


def build_runtime(
    settings: Settings,
    store: SessionService,
    mcp: McpService,
    skills: SkillService,
    client_tools: ClientToolService,
    approvals: Approvals,
    context_tokens: int | None = None,
    *,
    bots: BotService,
    subagent_logs: SessionService,
    secrets: SecretService,
    images: ImageService,
    files: ChatFileService,
) -> Runtime:
    """The default runtime: a model, the native tools, the guardrail, a durability checkpoint."""
    tool_service = ToolService(
        [
            clock_tool(),
            skill_save_tool(skills),
            skill_delete_tool(skills),
            skill_write_file_tool(skills),
            bot_create_tool(bots),
            fetch_with_secret_tool(secrets, bots, httpx.AsyncHTTPTransport()),
            send_file_tool(),
            extract_archive_tool(files, settings.files.max_bytes),
            make_archive_tool(files),
            *([view_image_tool(files)] if settings.llm.vision else []),
            *client_tools.tools(),
        ],
        approvals=approvals,
    )
    tool_service.add_provider(mcp.tools)
    tool_service.add_provider(lambda: [tool] if (tool := skill_tool(skills)) else [])

    logger.info("approval asks for: %s", sorted(approvals.tools_that_ask) or "nothing")
    _register_code_mode(tool_service, settings)

    client = OpenAIClient(settings.llm, read_image=images.read)
    runtime = Runtime(
        model=settings.llm.model,
        client=client,
        images=images if settings.llm.vision else None,
        tools=ToolPipeline(tool_service, DEFAULT_TOOLS),
        guidance=GUIDANCE,
        checkpoint=store.flush,
        context_tokens=context_tokens,
        hooks=default_hooks(),
        files=files,
    )
    _register_run_subagent(tool_service, runtime, subagent_logs)
    return runtime


def _register_code_mode(tool_service: ToolService, settings: Settings) -> None:
    for tool in code_mode_tools(
        tool_service=tool_service,
        runner=DenoRunner(
            deno_path=settings.code.deno_path,
            timeout_seconds=settings.code.timeout_seconds,
        ),
        withheld=NOT_CALLABLE_FROM_SCRIPTS,
    ):
        tool_service.register(tool)


def _register_run_subagent(
    tool_service: ToolService, runtime: Runtime, logs: SessionService
) -> None:
    subagent = dataclasses.replace(
        runtime,
        tools=ToolPipeline(tool_service, SUBAGENT_TOOLS),
        guidance=CODE_PROMPT,
    )
    tool_service.register(run_subagent_tool(Subagents(subagent, logs)))


def attach_bot_messages(
    tool_service: ToolService, sessions: SessionService, bots: BotService, runs: RunService
) -> BotMessages:
    """`message_bot` offered from `tool_service`, sending through the `BotMessages` it returns."""
    messages = BotMessages(sessions, bots, runs)
    tool_service.add_provider(lambda: [message_bot_tool(bots, messages)])
    return messages


def default_hooks() -> HookChain:
    """The four loop detectors, specific before general, and what to do about an empty reply."""
    return HookChain(
        (ExactFailureHook(), SameToolFailureHook(), NoProgressHook(), RepeatedCallHook()),
        step_hooks=(EmptyReplyHook(),),
    )
