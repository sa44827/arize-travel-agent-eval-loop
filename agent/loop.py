import json
from typing import cast

import anthropic
from openinference.instrumentation import OITracer
from opentelemetry import trace

from agent.config import MAX_TOKENS, MODEL
from agent.prompt import SYSTEM_PROMPT
from agent.tools import TOOLS, execute_tool

client = anthropic.Anthropic()

# `trace.get_tracer` is typed as returning a plain OTel Tracer, but Phoenix's
# `register()` installs an OpenInference provider globally, so what this
# actually resolves to at span-creation time is an OITracer — the thing that
# accepts `openinference_span_kind` and yields spans with set_input/set_output.
# The cast states that contract instead of hiding it behind a blanket ignore:
# if the tracer wiring ever changes, this line is where to look.
tracer = cast(OITracer, trace.get_tracer("travel-agent"))


def run_agent(messages: list) -> tuple[str, list]:
    """Run one user turn through the tool-calling loop.

    `messages` must end with the latest user message. Returns the assistant's
    reply text and the updated message history.
    """
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                with tracer.start_as_current_span(
                    block.name, openinference_span_kind="tool"
                ) as span:
                    span.set_input(block.input)
                    result = execute_tool(block.name, block.input)
                    span.set_output(result)
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
