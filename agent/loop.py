import json
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from typing import Any

import anthropic
from opentelemetry import trace

from agent.config import MAX_TOKENS, MODEL
from agent.prompt import system_prompt
from agent.tools import TOOLS, execute_tool

client = anthropic.Anthropic()


@contextmanager
def _tool_span(name: str, tool_input: Any) -> Iterator[Any]:
    """Span for one tool call, with the OpenInference extras when available.

    Tracing must stay optional. Phoenix's `register()` installs a provider whose
    tracer accepts `openinference_span_kind` and yields spans with set_input and
    set_output; with no provider installed — the CLI, a unit test, anyone who
    hasn't configured Phoenix — the same call resolves to a NoOpTracer that
    rejects those and raises. The agent must not depend on its observability
    stack being wired up to answer a question, so this degrades to a plain span
    instead of failing.
    """
    tracer = trace.get_tracer("travel-agent")
    with ExitStack() as stack:
        try:
            # ProxyTracer is lazy: it builds the context manager without
            # complaint and only delegates on __enter__, so the unsupported
            # kwarg surfaces there rather than at the call. Entering through
            # ExitStack is what puts the failure somewhere catchable.
            span = stack.enter_context(
                tracer.start_as_current_span(name, openinference_span_kind="tool")
            )
        except TypeError:
            span = stack.enter_context(tracer.start_as_current_span(name))

        if (set_input := getattr(span, "set_input", None)) is not None:
            set_input(tool_input)
        yield span


def _record_output(span: Any, result: Any) -> None:
    if (set_output := getattr(span, "set_output", None)) is not None:
        set_output(result)


def run_agent(messages: list) -> tuple[str, list]:
    """Run one user turn through the tool-calling loop.

    `messages` must end with the latest user message. Returns the assistant's
    reply text and the updated message history.
    """
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt(),
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                with _tool_span(block.name, block.input) as span:
                    result = execute_tool(block.name, block.input)
                    _record_output(span, result)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    reply = "".join(block.text for block in response.content if block.type == "text")
    return reply, messages
