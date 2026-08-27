from dotenv import load_dotenv
from backend.tracing import configure_tracing
import uuid

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

from agent.loop import run_agent
from common.logging import configure_logging
import logging

load_dotenv()
configure_logging()
tracer_provider = configure_tracing()
tracer = tracer_provider.get_tracer("travel-agent")
logger = logging.getLogger(__name__)


app = FastAPI(title="Travel Agent")
FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)


CONVERSATIONS: dict[str, list] = {}


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    conversation_id = req.conversation_id or str(uuid.uuid4())
    messages = CONVERSATIONS.get(conversation_id, [])
    messages.append({"role": "user", "content": req.message})
    with tracer.start_as_current_span(
        "travel_agent", openinference_span_kind="agent"
    ) as span:
        span.set_input(req.message)
        reply, messages = run_agent(messages)
        span.set_output(reply)
    CONVERSATIONS[conversation_id] = messages
    return ChatResponse(reply=reply, conversation_id=conversation_id)
