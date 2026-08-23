# Replacing Cordis in ~250 lines of Python

Cordis gives dsh five things. We need three of them, and each is small. This
file is the concrete substitute referenced by [DESIGN.md §2](../DESIGN.md).

| # | Cordis gives | Do we need it? | Substitute |
|---|---|---|---|
| 1 | Reversible registration (`ctx.effect`) | **Yes** | `Scope` + disposers (~60 lines) |
| 2 | Scoped visibility (per-agent layers) | **Yes** | `Layered` registry (~50 lines) |
| 3 | Typed events, 4 dispatch modes | **Yes** | `Events` bus (~70 lines) |
| 4 | Service registry + `inject` ordering | **No** | A composition root in Python |
| 5 | Config-driven composition, hot reload | **No** (v1) | Deferred; see §5 |

---

## 1. Reversible registration

The one rule: **every `register()` returns a function that undoes it**, and a
`Scope` collects them.

```python
from collections.abc import Awaitable, Callable
from typing import Any

type Disposer = Callable[[], None | Awaitable[None]]


async def _maybe_await(value: object) -> None:
    if isinstance(value, Awaitable):
        await value


class Scope:
    """One owner's registrations, and the boundary that unwinds them.

    Nesting is the point: disposing a parent disposes every child first, so a
    subagent's tools, listeners, and watchers cannot outlive the agent that
    created it. Disposal is reverse-order and idempotent.
    """

    def __init__(self, key: object, parent: "Scope | None" = None) -> None:
        self.key = key
        self.parent = parent
        self._disposers: list[Disposer] = []
        self._children: list[Scope] = []
        self._disposed = False
        if parent is not None:
            parent._children.append(self)

    def effect(self, setup: Callable[[], Disposer]) -> Disposer:
        """Run `setup` now; hold its disposer until this scope is disposed.

        Rejects after disposal rather than silently leaking a registration
        nothing will ever undo.
        """
        if self._disposed:
            raise RuntimeError(f"scope {self.key!r} is disposed")
        undo = setup()
        self._disposers.append(undo)
        return undo

    def child(self, key: object) -> "Scope":
        return Scope(key, parent=self)

    def chain(self) -> list[object]:
        """Scope keys from self outward: [self, parent, grandparent, ...]."""
        keys: list[object] = []
        cursor: Scope | None = self
        while cursor is not None:
            keys.append(cursor.key)
            cursor = cursor.parent
        return keys

    async def dispose(self) -> None:
        """Children first, then own disposers in reverse order.

        A raising disposer must not strand the rest, so each is isolated — the
        same fail-open discipline cell-bot's HookChain uses.
        """
        if self._disposed:
            return
        self._disposed = True
        for child in reversed(self._children):
            await child.dispose()
        for undo in reversed(self._disposers):
            try:
                await _maybe_await(undo())
            except Exception:
                logger.warning("disposer failed in scope %r", self.key, exc_info=True)
        self._disposers.clear()
        self._children.clear()
        if self.parent is not None and self in self.parent._children:
            self.parent._children.remove(self)
```

This is `ctx.effect()` plus recursive fiber disposal. It is also, near enough,
`contextlib.AsyncExitStack` with a parent pointer.

Usage — an MCP server becomes one effect instead of manual lifecycle code:

```python
def mount_mcp_server(scope: Scope, tools: Layered[ToolLike], config: McpServerConfig):
    def setup() -> Disposer:
        session = connect(config)
        undos = [tools.register(t.name, t, scope=scope) for t in session.list_tools()]
        def undo() -> None:
            for u in reversed(undos):
                u()
            session.close()
        return undo
    return scope.effect(setup)
```

Disposing the scope disconnects the server *and* removes its tools. Nothing
tracks that pairing by hand.

---

## 2. Scoped visibility

One registry, layered by scope. Lookup is nearest-first — a `ChainMap` where the
order is `[self, parent, ..., global]`.

```python
class Layered[V]:
    """Named entries in a global layer plus one layer per scope.

    Reads never create a layer; an emptied layer is reclaimed. A name registered
    in a nearer layer shadows the same name further out.
    """

    def __init__(self, on_change: Callable[[], None] = lambda: None) -> None:
        self._global: dict[str, V] = {}
        self._scoped: dict[object, dict[str, V]] = {}
        self._on_change = on_change

    def register(self, name: str, value: V, *, scope: Scope | None = None) -> Disposer:
        layer = self._global if scope is None else self._scoped.setdefault(scope.key, {})
        if name in layer:
            raise ValueError(f"{name!r} already registered in this layer")
        layer[name] = value

        done = False
        def undo() -> None:
            nonlocal done
            if done:
                return
            done = True
            layer.pop(name, None)
            if scope is not None and not layer:
                self._scoped.pop(scope.key, None)
            self._on_change()

        self._on_change()
        # Registering through a scope ties the entry's lifetime to it, so a
        # caller cannot forget to unregister. The returned disposer is for
        # callers that want to remove it sooner.
        return scope.effect(lambda: undo) if scope is not None else undo

    def resolve(self, scope: Scope | None) -> dict[str, V]:
        """The effective view for `scope`: global first, then each layer along
        the chain from farthest ancestor to nearest, so the nearest wins."""
        merged = dict(self._global)
        if scope is not None:
            for key in reversed(scope.chain()):        # farthest ancestor first
                merged.update(self._scoped.get(key, {}))
        return merged

    def own(self, scope: Scope) -> dict[str, V]:
        """This scope's OWN entries, chain-blind.

        Capabilities inherit down the chain; restrictions and guards must not —
        a parent's tool filter is not something the child declared.
        """
        return dict(self._scoped.get(scope.key, {}))
```

That is the whole shadowing mechanism: `dict.update` in the right order.

```python
tools.register("read", read_tool)                       # global
tools.register("write", write_tool)                     # global
tools.register("web_search", search_tool, scope=research)
tools.register("write", refuse_tool, scope=research)     # shadows global

tools.resolve(None)      # read, write
tools.resolve(research)  # read, write→refuse, web_search
```

---

## 3. Events

Three dispatch modes cover what the loop needs. **Waterfall is the important
one** — it is around-middleware, and it is how policy plugins intercept without
the loop knowing they exist.

```python
_UNSET = object()


class Events:
    """Scoped listener registry with observe / waterfall / serial dispatch.

    Scope filtering matches dsh: a listener registered on an enclosing scope
    receives its descendants' events; a sibling's listener never does. Events
    flow up the chain, never down.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, list[tuple[object | None, Callable]]] = {}

    def on(self, event: str, fn: Callable, *, scope: Scope | None = None) -> Disposer:
        entry = (scope.key if scope else None, fn)
        bucket = self._listeners.setdefault(event, [])
        bucket.append(entry)
        def undo() -> None:
            if entry in bucket:
                bucket.remove(entry)
        return scope.effect(lambda: undo) if scope is not None else undo

    def _for(self, event: str, scope: Scope | None) -> list[Callable]:
        chain = set(scope.chain()) if scope is not None else set()
        return [
            fn for key, fn in self._listeners.get(event, [])
            if key is None or key in chain      # untagged = global; tagged = self or ancestor
        ]

    async def emit(self, event: str, scope: Scope | None = None, **kw) -> None:
        """Observers. Every listener runs; one failure never stops the others."""
        for fn in self._for(event, scope):
            try:
                await _maybe_await(fn(**kw))
            except Exception:
                logger.warning("listener failed for %r", event, exc_info=True)

    async def waterfall(self, event: str, value, scope: Scope | None = None, **kw):
        """Around-middleware. A listener receives (value, next, **kw):
        `await next()` delegates and returns the downstream result;
        `await next(replacement)` delegates a rewritten value;
        returning WITHOUT calling next short-circuits and owns the decision.

        Deliberately NOT isolated like emit(): a waterfall listener that raises
        has taken no decision and left the chain broken, so it propagates.
        """
        listeners = self._for(event, scope)

        async def step(i: int, current):
            if i == len(listeners):
                return current
            async def nxt(replacement=_UNSET):
                return await step(i + 1, current if replacement is _UNSET else replacement)
            return await listeners[i](current, nxt, **kw)

        return await step(0, value)

    async def serial(self, event: str, scope: Scope | None = None, **kw):
        """Ordered, awaited, first non-None wins. This is cell-bot's HookChain
        decision semantics — ordering IS precedence."""
        for fn in self._for(event, scope):
            try:
                result = await _maybe_await(fn(**kw))
            except Exception:
                logger.warning("listener failed for %r", event, exc_info=True)
                continue
            if result is not None:
                return result
        return None
```

The tool pipeline then needs no special machinery:

```python
async def execute_tool(call, scope):
    async def run(exec_, next_):
        return await toolbox.dispatch(exec_)
    events.on("tools/execute", run)                    # the base implementation

    return await events.waterfall("tools/execute", call, scope=scope)
```

…and a timeout policy, an approval gate, or a guardrail each become one listener
that wraps `next()` — exactly dsh's `timeout-policy` and `sandbox-policy`
packages, without the framework.

---

## 4. What we drop: services and `inject`

`inject` solves a problem we don't have. Cordis needs it because plugins load
from **config at runtime in unknown order** — a plugin must wait for `ctx.tools`
to exist, and unload if it disappears.

We wire in Python, in one place, in a known order. A missing dependency is a
`TypeError` at startup, not a `PENDING` fiber:

```python
@dataclass(frozen=True)
class Ctx:
    """Everything a plugin may reach. Not a service locator — a wiring record.

    Frozen and fully constructed, so 'is this available?' is answered by the
    type checker rather than at runtime.
    """
    scope: Scope
    events: Events
    tools: Layered[ToolLike]
    prompt_sections: Layered[PromptSection]
    skills: Layered[SkillProvider]
    llm: LLMClient
    sessions: SessionStore


def compose(settings: Settings) -> Ctx:
    root = Scope(key="root")
    events = Events()
    ctx = Ctx(
        scope=root, events=events,
        tools=Layered(on_change=lambda: events.emit_sync("tools/change")),
        prompt_sections=Layered(),
        skills=Layered(),
        llm=OpenAIClient(settings.llm),
        sessions=SessionStore(JsonlPersistence(settings.home / "sessions")),
    )
    mount_fs_tools(ctx)
    mount_shell_tools(ctx)
    mount_skills(ctx, settings.skills)
    for server in settings.mcp_servers:
        mount_mcp_server(root, ctx.tools, server)
    return ctx
```

`compose()` is our `cordis.yml`. It is less flexible and considerably easier to
read, debug, and type-check.

Per-agent composition is the same function against a child scope:

```python
def compose_agent(ctx: Ctx, agent: Agent, preset: Preset) -> Scope:
    scope = ctx.scope.child(agent)          # the Agent object is its own key
    for tool in preset.extra_tools:
        ctx.tools.register(tool.name, tool, scope=scope)
    if preset.skill_dirs:
        ctx.skills.register("filesystem", FsSkills(preset.skill_dirs), scope=scope)
    return scope                            # dispose it to unwind all of the above
```

---

## 5. What we genuinely lose

Honest list. None of these block v1.

| Lost | Impact | If we need it later |
|---|---|---|
| **Hot reload (HMR)** | Restart to pick up code changes | Real cost in dev only; dsh needed it because config edits remount plugins live |
| **Third-party plugins without code changes** | An outside author cannot ship a package we mount from config | Add a config-driven `mount()` registry later — the `Scope`/`Layered` primitives already support it |
| **Config-as-data composition** | `compose()` is code, not YAML | Same as above; the composition root can read a config file when there is a reason to |
| **`inject` / PENDING waiting** | None — we wire in order | n/a |
| **`parallel` dispatch mode** | Not needed by the loop | Trivial to add: `asyncio.gather` over `_for()` |

The one that matters strategically is **third-party plugins**. dsh's whole
`dsh plugin add` story depends on config-driven mounting. If cell-harness ever
wants an ecosystem, that's the piece to add — and the `Scope` + `Layered` +
`Events` primitives above are exactly what it would be built on. Nothing here
forecloses it.

---

## 6. Build order

All of this lands in **phase 1** of [DESIGN.md §5](../DESIGN.md#5-build-order),
alongside the event log:

1. `Scope` + `Disposer`
2. `Layered`
3. `Events` (emit / waterfall / serial)
4. `Ctx` + `compose()`

~250 lines, no dependencies. Then **route every registration through them from
day one**, even while there is one agent and one layer. Retrofitting scope onto
registries that assumed a flat dict means touching every registry — the same
category of expensive mistake as retrofitting the event log.
