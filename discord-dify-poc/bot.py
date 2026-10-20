"""Discord Bot PoC: @AIAssistant → Dify Hello Agent → reply in same Forum post/thread.

Handles:
  - replies inside an existing Forum post (on_message)
  - the first message when creating a new Forum post (on_thread_create)
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import discord
import httpx
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "http://localhost/v1").rstrip("/")
DIFY_API_KEY = os.environ["DIFY_API_KEY"]
POC_FORUM_CHANNEL_ID = os.getenv("POC_CHANNEL_ID", "").strip()
TRIGGER_TAGS = {
    t.strip().lower()
    for t in os.getenv("AI_TRIGGER_TAGS", "AIAssistant,@AIAssistant").split(",")
    if t.strip()
}

_conversations: dict[str, str] = {}
_handled_message_ids: set[int] = set()


async def ask_dify(query: str, *, user_id: str, conversation_id: str = "") -> tuple[str, str]:
    payload: dict[str, Any] = {
        "inputs": {},
        "query": query,
        "response_mode": "streaming",
        "user": user_id,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    agent_parts: list[str] = []
    message_parts: list[str] = []
    new_conv = conversation_id

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{DIFY_BASE_URL}/chat-messages",
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if event.get("conversation_id"):
                    new_conv = event["conversation_id"]
                answer = event.get("answer")
                if not answer:
                    continue
                if event.get("event") == "agent_message":
                    agent_parts.append(answer)
                elif event.get("event") == "message":
                    message_parts.append(answer)

    text = "".join(agent_parts or message_parts).strip()
    return text or "(κενή απάντηση από το Agent)", new_conv


def _is_triggered(message: discord.Message, bot_user: discord.ClientUser) -> bool:
    if bot_user in message.mentions:
        return True
    content_lower = message.content.lower()
    for tag in TRIGGER_TAGS:
        if tag.lstrip("@") and tag.lstrip("@") in content_lower.replace("@", ""):
            if tag.startswith("@"):
                if tag.lower() in content_lower:
                    return True
            elif re.search(rf"(?<!\w)@?{re.escape(tag)}(?!\w)", content_lower):
                return True
    return False


def _clean_query(content: str, bot_user: discord.ClientUser) -> str:
    text = re.sub(rf"<@!?{bot_user.id}>", "", content)
    for tag in TRIGGER_TAGS:
        text = re.sub(re.escape(tag), "", text, flags=re.IGNORECASE)
        text = re.sub(re.escape(tag.lstrip("@")), "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _channel_in_scope(channel: discord.abc.Messageable) -> bool:
    if isinstance(channel, discord.DMChannel):
        return True
    if not POC_FORUM_CHANNEL_ID:
        return True
    parent = getattr(channel, "parent", None)
    if parent is not None and str(parent.id) == POC_FORUM_CHANNEL_ID:
        return True
    if hasattr(channel, "id") and str(channel.id) == POC_FORUM_CHANNEL_ID:
        return True
    return False


class AIAssistantBot(discord.Client):
    async def on_ready(self) -> None:
        assert self.user is not None
        print(f"Logged in as {self.user} (id={self.user.id})", flush=True)
        print(f"Mention: @{self.user.name}  |  triggers: {sorted(TRIGGER_TAGS)}", flush=True)
        print(f"Forum filter: {POC_FORUM_CHANNEL_ID or 'all channels'}", flush=True)
        print(f"Dify: {DIFY_BASE_URL}", flush=True)

    async def on_message(self, message: discord.Message) -> None:
        await self._handle_user_message(message, source="message")

    async def on_thread_create(self, thread: discord.Thread) -> None:
        """Forum post opener: starter message often misses on_message."""
        parent = thread.parent
        if not isinstance(parent, discord.ForumChannel):
            return
        if POC_FORUM_CHANNEL_ID and str(parent.id) != POC_FORUM_CHANNEL_ID:
            return

        starter = thread.starter_message
        if starter is None:
            try:
                # In forum posts, starter message id == thread id
                starter = await thread.fetch_message(thread.id)
            except discord.HTTPException as exc:
                print(f"thread_create: cannot fetch starter for {thread.id}: {exc}", flush=True)
                return

        print(f"thread_create: starter in {thread.id}", flush=True)
        await self._handle_user_message(starter, source="thread_create")

    async def _handle_user_message(self, message: discord.Message, *, source: str) -> None:
        if message.author.bot or self.user is None:
            return
        if message.id in _handled_message_ids:
            return
        if not _channel_in_scope(message.channel):
            print(f"skip out-of-scope ch={getattr(message.channel, 'id', '?')}", flush=True)
            return
        if not _is_triggered(message, self.user):
            return

        _handled_message_ids.add(message.id)
        if len(_handled_message_ids) > 5000:
            _handled_message_ids.clear()

        query = _clean_query(message.content, self.user)
        print(
            f"[{source}] triggered by {message.author} in {message.channel.id}: {query[:120]!r}",
            flush=True,
        )
        if not query:
            await message.reply(
                "Γράψε την ερώτηση μετά το tag, π.χ. `@AIAssistant τι είναι το Emblem;`"
            )
            return

        thread_key = str(message.channel.id)
        conv = _conversations.get(thread_key, "")

        try:
            async with message.channel.typing():
                answer, new_conv = await ask_dify(
                    query,
                    user_id=f"discord-{message.channel.id}",
                    conversation_id=conv,
                )
                _conversations[thread_key] = new_conv
        except Exception as exc:
            print(f"Dify/Discord error: {exc!r}", flush=True)
            if conv:
                try:
                    _conversations.pop(thread_key, None)
                    async with message.channel.typing():
                        answer, new_conv = await ask_dify(
                            query,
                            user_id=f"discord-{message.channel.id}",
                            conversation_id="",
                        )
                        _conversations[thread_key] = new_conv
                except Exception as exc2:
                    await message.reply(f"Σφάλμα: `{exc2}`")
                    return
            else:
                await message.reply(f"Σφάλμα: `{exc}`")
                return

        print(f"replying ({len(answer)} chars)", flush=True)
        if len(answer) <= 1900:
            await message.reply(answer)
        else:
            chunks = [answer[i : i + 1900] for i in range(0, len(answer), 1900)]
            await message.reply(chunks[0])
            for chunk in chunks[1:]:
                await message.channel.send(chunk)


def main() -> None:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guilds = True
    bot = AIAssistantBot(intents=intents)
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
