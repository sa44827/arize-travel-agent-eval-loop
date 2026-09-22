import logging

from google import genai
from google.genai import types

from agent.config import MAX_OUTPUT_TOKENS, MAX_STEPS, MODEL, PROMPT_VERSION, REQUEST_TIMEOUT_MS
from agent.prompt import get_system_prompt
from agent.tools import TOOLS, execute_tool
from agent.tracing import tracer

log = logging.getLogger(__name__)

# Reads GEMINI_API_KEY from the environment. The SDK retries 429/5xx with backoff.
client = genai.Client(
    http_options=types.HttpOptions(
        timeout=REQUEST_TIMEOUT_MS,
        retry_options=types.HttpRetryOptions(
            attempts=4, initial_delay=2.0, http_status_codes=[429, 500, 502, 503, 504]
        ),
    )
)

CONFIG = types.GenerateContentConfig(
    system_instruction=get_system_prompt(PROMPT_VERSION),
    tools=[
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t["description"],
                    parameters_json_schema=t["input_schema"],
                )
                for t in TOOLS
            ]
        )
    ],
    max_output_tokens=MAX_OUTPUT_TOKENS,
    # We run the tool loop ourselves so every tool call is an explicit, traceable step.
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)

FALLBACK_REPLY = "Sorry, I ran into a problem putting that together. Please try again."


def _to_contents(messages: list) -> list[types.Content]:
    """Accept plain {"role", "content": str} dicts (as chat.py/api.py append) or Content objects."""
    contents = []
    for m in messages:
        if isinstance(m, types.Content):
            contents.append(m)
        else:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))
    return contents


def _run_tool(name: str, args: dict):
    with tracer.start_as_current_span(name, openinference_span_kind="tool") as span:
        span.set_tool(name=name, parameters=args)
        span.set_input(args, mime_type="application/json")
        result = execute_tool(name, args)
        span.set_output(result, mime_type="application/json")
        return result


def run_agent(messages: list) -> tuple[str, list]:
    """Run one user turn through the tool-calling loop.

    `messages` must end with the latest user message. Returns the assistant's
    reply text and the updated message history.
    """
    last = messages[-1]
    user_text = last["content"] if isinstance(last, dict) else ""
    with tracer.start_as_current_span("agent_turn", openinference_span_kind="agent") as span:
        span.set_input(user_text)
        reply, history, fallback = _run_turn(messages)
        span.set_output(reply)
        span.set_attribute("agent.fallback", fallback)
        return reply, history


def _run_turn(messages: list) -> tuple[str, list, bool]:
    contents = _to_contents(messages)
    try:
        for _ in range(MAX_STEPS):
            response = client.models.generate_content(
                model=MODEL, contents=contents, config=CONFIG
            )
            model_content = response.candidates[0].content
            contents.append(model_content)

            calls = response.function_calls
            if not calls:
                return response.text or "", contents, False

            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=call.name, response={"result": _run_tool(call.name, dict(call.args or {}))}
                        )
                        for call in calls
                    ],
                )
            )
        log.warning("agent hit MAX_STEPS=%d without a final answer", MAX_STEPS)
    except Exception:
        log.exception("agent turn failed")

    # Failed turn: keep the caller's history clean (no dangling tool calls).
    return FALLBACK_REPLY, messages + [{"role": "assistant", "content": FALLBACK_REPLY}], True
