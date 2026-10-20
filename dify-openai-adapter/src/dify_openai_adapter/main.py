"""OpenAI-compatible adapter for Dify Agents."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from httpx import HTTPStatusError
from pydantic import BaseModel, Field

from dify_openai_adapter.config import get_settings
from dify_openai_adapter.dify_client import (
    dify_chat_blocking,
    dify_chat_streaming,
    extract_query,
    extract_user_id,
)

app = FastAPI(
    title="Dify OpenAI Adapter",
    version="0.1.0",
    description="Translates OpenAI /v1 calls to Dify /v1/chat-messages",
)


class ChatMessage(BaseModel):
    role: str
    content: Any = ""


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    user: str | None = None
    # Optional passthrough for Dify multi-turn (OpenWebUI won't send this yet)
    conversation_id: str | None = None


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    agents = settings.agent_map()
    return {
        "status": "ok",
        "service": "dify-openai-adapter",
        "dify_base_url": settings.dify_base_url,
        "models_configured": sorted(agents.keys()),
        "models_count": len(agents),
    }


@app.get("/v1/models")
def list_models() -> dict:
    settings = get_settings()
    created = int(time.time())
    data = [
        {
            "id": model_id,
            "object": "model",
            "created": created,
            "owned_by": "dify-adapter",
        }
        for model_id in sorted(settings.agent_map().keys())
    ]
    return {"object": "list", "data": data}


def _resolve_api_key(model_id: str) -> str:
    settings = get_settings()
    key = settings.api_key_for_model(model_id)
    if not key or key.startswith("app-REPLACE"):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown or unconfigured model: {model_id}. Edit agents.json.",
        )
    return key


def _openai_completion(model: str, answer: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }


def _openai_chunk(
    *,
    completion_id: str,
    model: str,
    content: str | None,
    finish_reason: Literal["stop"] | None,
) -> str:
    delta: dict[str, Any] = {}
    if content is not None:
        delta["content"] = content
    if finish_reason is None and content is not None and content == "":
        delta = {"role": "assistant", "content": ""}
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest):
    settings = get_settings()
    api_key = _resolve_api_key(body.model)
    messages = [m.model_dump() for m in body.messages]
    query = extract_query(messages)
    if not query:
        raise HTTPException(status_code=400, detail="No user message found")

    user = body.user or extract_user_id(messages)
    conversation_id = body.conversation_id or ""

    if not body.stream:
        try:
            data = await dify_chat_blocking(
                settings=settings,
                api_key=api_key,
                query=query,
                user=user,
                conversation_id=conversation_id,
            )
        except HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc

        answer = data.get("answer") or ""
        return _openai_completion(body.model, answer)

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    async def event_stream():
        yield _openai_chunk(
            completion_id=completion_id,
            model=body.model,
            content="",
            finish_reason=None,
        )
        try:
            # Prefer incremental agent_message; ignore the later full ``message``
            # event so OpenWebUI does not see the answer twice.
            saw_agent_chunks = False
            async for event in dify_chat_streaming(
                settings=settings,
                api_key=api_key,
                query=query,
                user=user,
                conversation_id=conversation_id,
            ):
                etype = event.get("event")
                if etype == "agent_message":
                    piece = event.get("answer") or ""
                    if piece:
                        saw_agent_chunks = True
                        yield _openai_chunk(
                            completion_id=completion_id,
                            model=body.model,
                            content=piece,
                            finish_reason=None,
                        )
                elif etype == "message" and not saw_agent_chunks:
                    piece = event.get("answer") or ""
                    if piece:
                        yield _openai_chunk(
                            completion_id=completion_id,
                            model=body.model,
                            content=piece,
                            finish_reason=None,
                        )
                elif etype == "error":
                    msg = event.get("message") or event.get("code") or "dify error"
                    yield _openai_chunk(
                        completion_id=completion_id,
                        model=body.model,
                        content=f"\n[Error: {msg}]",
                        finish_reason=None,
                    )
                elif etype == "message_end":
                    break
        except HTTPStatusError as exc:
            yield _openai_chunk(
                completion_id=completion_id,
                model=body.model,
                content=f"\n[HTTP {exc.response.status_code}: {exc.response.text[:200]}]",
                finish_reason=None,
            )

        yield _openai_chunk(
            completion_id=completion_id,
            model=body.model,
            content=None,
            finish_reason="stop",
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
