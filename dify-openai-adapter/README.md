# dify-openai-adapter

OpenAI-compatible front for Dify Agents (`/v1/chat-messages`).

Used so OpenWebUI (and any OpenAI client) can call Dify Agents with Skills + RAG.

## Setup

```bash
cd dify-openai-adapter
cp .env.example .env
cp agents.json.example agents.json
# edit agents.json — put real Dify app-… keys
uv sync
```

## Run

```bash
uv run uvicorn dify_openai_adapter.main:app --app-dir src --host 127.0.0.1 --port 8085 --reload
```

Check:

```bash
curl -s http://127.0.0.1:8085/health
curl -s http://127.0.0.1:8085/v1/models
```

Chat (needs real `app-…` in `agents.json` + reachable Dify):

```bash
curl -s http://127.0.0.1:8085/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"marketing-agent","messages":[{"role":"user","content":"γεια"}]}'
```
