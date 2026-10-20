"""PoC: Dify Hello Agent → Discord post via webhook.

No Discord Bot token needed — only a channel webhook URL.

Usage:
  python post_poc.py "Γεια σου, ποιος είσαι;"
  python post_poc.py   # interactive prompt
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "http://localhost/v1").rstrip("/")
DIFY_API_KEY = os.environ["DIFY_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


def ask_dify(query: str, *, user_id: str = "discord-poc") -> str:
    payload: dict[str, Any] = {
        "inputs": {},
        "query": query,
        "response_mode": "streaming",
        "user": user_id,
    }
    agent_parts: list[str] = []
    message_parts: list[str] = []

    with httpx.Client(timeout=120.0) as client:
        with client.stream(
            "POST",
            f"{DIFY_BASE_URL}/chat-messages",
            headers={
                "Authorization": f"Bearer {DIFY_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                answer = event.get("answer")
                if not answer:
                    continue
                if event.get("event") == "agent_message":
                    agent_parts.append(answer)
                elif event.get("event") == "message":
                    message_parts.append(answer)

    text = "".join(agent_parts or message_parts).strip()
    return text or "(κενή απάντηση από το Agent)"


def post_to_discord(*, question: str, answer: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise SystemExit(
            "Λείπει DISCORD_WEBHOOK_URL στο .env\n"
            "Discord Forum channel → Edit Channel → Integrations → Webhooks → Copy URL"
        )

    # Discord webhook limit ~2000 chars per content; thread_name → Forum post
    content = f"**Ερώτηση:** {question}\n**Dify Hello:** {answer}"
    if len(content) > 1900:
        content = content[:1890] + "…"

    title = question.strip().replace("\n", " ")
    if len(title) > 90:
        title = title[:87] + "…"
    if not title:
        title = "Dify Hello PoC"

    # wait=true so we get the created message/thread back
    url = DISCORD_WEBHOOK_URL
    if "wait=" not in url:
        url = f"{url}{'&' if '?' in url else '?'}wait=true"

    payload = {
        "username": "Dify Hello PoC",
        "content": content,
        "thread_name": title,  # required for Forum channel posts
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            print(f"Discord error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
        data = resp.json() if resp.content else {}
        thread_id = data.get("channel_id") or data.get("id")
        print(f"✓ Forum post created (thread/channel id: {thread_id})")


def main() -> None:
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
    else:
        question = input("Ερώτηση για τον Agent: ").strip()

    if not question:
        raise SystemExit("Άδεια ερώτηση.")

    print("→ Asking Dify Hello…")
    answer = ask_dify(question)
    print(f"← {answer}\n")
    post_to_discord(question=question, answer=answer)


if __name__ == "__main__":
    main()
