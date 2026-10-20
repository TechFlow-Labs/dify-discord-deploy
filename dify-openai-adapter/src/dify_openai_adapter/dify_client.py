"""HTTP client: OpenAI-shaped requests → Dify /v1/chat-messages."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from dify_openai_adapter.config import Settings


_HISTORY_CHAR_BUDGET = 24000


def _message_text(content: Any) -> str:
    if isinstance(content, list):
        parts = [
            p.get("text", "")
            for p in content
            if isinstance(p, dict) and p.get("type") == "text"
        ]
        return "\n".join(parts).strip()
    return str(content or "").strip()


def extract_query(messages: list[dict[str, Any]]) -> str:
    """Send the latest request plus earlier turns.

    Dify only stores history when it receives a conversation id. OpenWebUI
    sends the thread on every call and no Dify id, so a follow-up such as
    "put the above in a file" would otherwise arrive with no prior answer.
    """
    turns: list[tuple[str, str]] = []
    for msg in messages:
        role = msg.get("role")
        if role not in {"user", "assistant"}:
            continue
        text = _message_text(msg.get("content"))
        if text:
            turns.append((role, text))
    if not turns:
        return ""

    last_user_at = max((i for i, (role, _) in enumerate(turns) if role == "user"), default=None)
    if last_user_at is None:
        return ""
    request = turns[last_user_at][1]
    prior = turns[:last_user_at]
    if not prior:
        return request

    blocks: list[str] = []
    used = 0
    for role, text in reversed(prior):
        label = "User" if role == "user" else "Assistant"
        block = f"{label}: {text}"
        if used and used + len(block) > _HISTORY_CHAR_BUDGET:
            break
        blocks.append(block)
        used += len(block)
    history = "\n\n".join(reversed(blocks))
    return (
        "Conversation so far:\n"
        f"{history}\n\n"
        "Current request:\n"
        f"{request}"
    )


def extract_user_id(messages: list[dict[str, Any]], fallback: str = "openwebui") -> str:
    """Optional: honor a system message like user:xyz — else default."""
    return fallback


async def dify_chat_blocking(
    *,
    settings: Settings,
    api_key: str,
    query: str,
    user: str,
    conversation_id: str = "",
) -> dict[str, Any]:
    """Aggregate a streaming Dify response into a single answer.

    Agent Apps reject ``response_mode=blocking``, so we always stream under the
    hood and return ``{"answer": ...}`` for OpenAI non-stream callers.
    """
    # Agent Apps emit incremental ``agent_message`` chunks, then a full
    # ``message`` event with the same text. Prefer agent chunks; fall back to
    # the final ``message`` answer if no chunks arrived.
    parts: list[str] = []
    full_answer = ""
    meta: dict[str, Any] = {}
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
                parts.append(piece)
        elif etype == "message":
            full_answer = event.get("answer") or full_answer
        elif etype == "error":
            msg = event.get("message") or event.get("code") or "dify error"
            raise httpx.HTTPStatusError(
                f"Dify error: {msg}",
                request=httpx.Request("POST", f"{settings.dify_base_url}/chat-messages"),
                response=httpx.Response(400, text=str(msg)),
            )
        elif etype == "message_end":
            meta = event
            break
    answer = "".join(parts) if parts else full_answer
    return {"answer": answer, "message_end": meta}


async def dify_chat_streaming(
    *,
    settings: Settings,
    api_key: str,
    query: str,
    user: str,
    conversation_id: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """Yield parsed Dify SSE event objects."""
    url = f"{settings.dify_base_url}/chat-messages"
    payload: dict[str, Any] = {
        "inputs": {},
        "query": query,
        "response_mode": "streaming",
        "user": user,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                if line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue
