"""The runtime the server composes: a model, the native tools, the guardrail."""

from __future__ import annotations

import dataclasses
import functools
import logging
from collections.abc import Sequence

import httpx

from harness.bots import BotService, GroupService
from harness.config.sections import CompactionSettings
from harness.config.settings import Settings
from harness.files import ChatFileService
from harness.images import ImageService
from harness.llm import LLMClient
from harness.llm.adapters import OpenAIClient, OpenAISettings, context_window_tokens
from harness.mcp import McpService
from harness.prompts import CODE_PROMPT
from harness.runs.service.bot_messages import BotMessenger, Follow
from harness.runs.service.run_service import RunService
from harness.runtime.hooks import HookChain
from harness.runtime.hooks.native.empty_reply import EmptyReplyHook
from harness.runtime.hooks.native.exact_failure import ExactFailureHook
from harness.runtime.hooks.native.no_progress import NoProgressHook
from harness.runtime.hooks.native.no_wait import NoWaitHook
from harness.runtime.hooks.native.repeated_call import RepeatedCallHook
from harness.runtime.hooks.native.same_tool_failure import SameToolFailureHook
from harness.runtime.hooks.native.skill_list import SkillListHook
from harness.runtime.service import Runtime, session_chat_id
from harness.runtime.subagents import Subagents
from harness.sandbox import DenoRunner
from harness.schedules import ScheduleService
from harness.secrets import SecretService
from harness.session.service.session_service import SessionService
from harness.skills import SKILL, SkillService, skill_tool
from harness.tickets.domain.prompts import ORCHESTRATOR_INTRO
from harness.tools import ApprovalService, ToolService, Toolset
from harness.tools.client import ClientToolCatalog, ClientToolService
from harness.tools.native.bots import BOT_CREATE, MESSAGE_BOT, bot_create_tool, message_bot_tool
from harness.tools.native.clock import get_current_time_tool
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
from harness.tools.native.schedule import (
    SCHEDULE_CREATE,
    SCHEDULE_EDIT,
    SCHEDULE_LIST,
    SCHEDULE_VIEW,
    schedule_create_tool,
    schedule_edit_tool,
    schedule_list_tool,
    schedule_view_tool,
)
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
from harness.tools.native.tickets import TICKET_NOTE, TICKET_REPORT, TICKET_ROUTE
from harness.tools.service.tool_service import Disposer
from harness.web.model_choice import CredentialModels, ModelEndpoint

logger = logging.getLogger("harness.web")

CLIENT_TOOLS = ClientToolCatalog(
    (GET_LOCATION_TOOL, ASK_USER_TOOL, ASK_FOR_SECRET_TOOL, HAND_OVER_TOOL)
)
SKILL_WRITE_TOOLS = (SKILL_SAVE, SKILL_DELETE, SKILL_WRITE_FILE)
SCHEDULE_TOOLS = (SCHEDULE_CREATE, SCHEDULE_LIST, SCHEDULE_VIEW, SCHEDULE_EDIT)
DEFAULT_TOOLS = (
    SKILL,
    *SKILL_WRITE_TOOLS,
    BOT_CREATE,
    MESSAGE_BOT,
    *SCHEDULE_TOOLS,
    TICKET_ROUTE,
    TICKET_NOTE,
    SEND_FILE,
    VIEW_IMAGE,
)
WORK_TOOLS = (RUN_SUBAGENT, FETCH_WITH_SECRET, EXTRACT_ARCHIVE, MAKE_ARCHIVE)
SUBAGENT_TOOLS = (LIST_FUNCTIONS, GET_FUNCTION_DETAILS, EXECUTE_TYPESCRIPT, SKILL)
SIGHT_TOOLS = frozenset({VIEW_IMAGE})
NOT_CALLABLE_FROM_SCRIPTS = frozenset(
    {
        SKILL,
        *SKILL_WRITE_TOOLS,
        BOT_CREATE,
        MESSAGE_BOT,
        *SCHEDULE_TOOLS,
        RUN_SUBAGENT,
        TICKET_ROUTE,
        TICKET_NOTE,
        TICKET_REPORT,
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
    sessions: SessionService,
    mcp: McpService,
    skills: SkillService,
    client_tools: ClientToolService,
    approvals: ApprovalService,
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
            get_current_time_tool(),
            skill_save_tool(skills),
            skill_delete_tool(skills),
            skill_write_file_tool(skills),
            fetch_with_secret_tool(secrets, bots, httpx.AsyncHTTPTransport()),
            send_file_tool(),
            extract_archive_tool(files, settings.files.max_bytes),
            make_archive_tool(files),
            view_image_tool(files),
            *CLIENT_TOOLS.tools(),
        ],
        approvals=approvals,
    )
    tool_service.add_provider(mcp.tools)
    tool_service.add_provider(lambda: [tool] if (tool := skill_tool(skills)) else [])
    tool_service.add_provider(lambda: [tool] if (tool := bot_create_tool(bots, secrets)) else [])

    logger.info("approval asks for: %s", sorted(approvals.protected_tools) or "nothing")
    _register_code_mode(tool_service, settings)

    runtime = Runtime(
        models=CredentialModels(
            secrets,
            bots,
            settings.llm,
            ModelEndpoint(
                client_for=functools.partial(_openai_client, images),
                blocking_window_for=functools.partial(
                    compaction_window_tokens, settings.compaction
                ),
            ),
        ),
        images=images,
        tools=Toolset(
            tool_service, DEFAULT_TOOLS, sight_tools=SIGHT_TOOLS, can_reach_servers=False
        ),
        guidance=ORCHESTRATOR_INTRO,
        checkpoint=sessions.flush,
        hooks=orchestrator_hooks(skills),
        files=files,
        server_instructions=mcp.instructions,
        chat_id_for=session_chat_id,
    )
    _register_run_subagent(tool_service, runtime, subagent_logs)
    return runtime


def _openai_client(images: ImageService, settings: OpenAISettings) -> LLMClient:
    return OpenAIClient(settings, read_image=images.read)


def compaction_window_tokens(
    compaction: CompactionSettings, settings: OpenAISettings
) -> int | None:
    """The window `settings`'s model compacts at: the configured one, else its endpoint's report."""
    configured = compaction.context_tokens
    if configured is not None:
        logger.info(
            "compaction: %s has a %d-token window (from config)", settings.model, configured
        )
        return configured
    discovered = context_window_tokens(settings)
    if discovered is None:
        logger.warning(
            "compaction: %s at %s reports no window and none is configured; automatic "
            "compaction is off for it, only a provider overflow triggers it",
            settings.model,
            settings.base_url,
        )
    else:
        logger.info(
            "compaction: %s has a %d-token window (reported by endpoint)",
            settings.model,
            discovered,
        )
    return discovered


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
    subagent = delegate_runtime(tool_service, runtime, SUBAGENT_TOOLS)
    tool_service.register(run_subagent_tool(Subagents(subagent, logs)))


def delegate_runtime(tool_service: ToolService, runtime: Runtime, tools: Sequence[str]) -> Runtime:
    """`runtime` as a subagent or a ticket's worker runs it: offered `tools`, free to wait."""
    hooks = runtime.hooks
    kept = tuple(hook for hook in hooks.tool_hooks if not isinstance(hook, NoWaitHook))
    return dataclasses.replace(
        runtime,
        tools=Toolset(tool_service, tools, sight_tools=SIGHT_TOOLS, can_reach_servers=True),
        guidance=CODE_PROMPT,
        hooks=dataclasses.replace(hooks, tool_hooks=kept),
    )


def attach_bot_messages(
    tool_service: ToolService,
    bots: BotService,
    runs: RunService,
    *,
    follow: Follow,
) -> BotMessenger:
    """`message_bot` offered from `tool_service`, sending through the `BotMessenger` it returns."""
    messages = BotMessenger(bots, runs, follow=follow)
    tool_service.add_provider(lambda: [message_bot_tool(bots, messages)])
    return messages


def attach_schedules(
    tool_service: ToolService, groups: GroupService, schedules: ScheduleService
) -> Disposer:
    """The schedule tools offered from `tool_service`; the disposer takes them back."""
    return tool_service.add_provider(
        lambda: [
            schedule_create_tool(groups, schedules),
            schedule_list_tool(groups, schedules),
            schedule_view_tool(groups, schedules),
            schedule_edit_tool(groups, schedules),
        ]
    )


def default_hooks(skills: SkillService) -> HookChain:
    """The loop detectors, specific before general, then the empty-reply and skill-list hooks."""
    return HookChain(
        (ExactFailureHook(), SameToolFailureHook(), NoProgressHook(), RepeatedCallHook()),
        step_hooks=(EmptyReplyHook(), SkillListHook(skills)),
    )


def orchestrator_hooks(skills: SkillService) -> HookChain:
    """`default_hooks` behind the no-wait guard, which only the bot's own turns get."""
    hooks = default_hooks(skills)
    return dataclasses.replace(hooks, tool_hooks=(NoWaitHook(), *hooks.tool_hooks))
