# Local split — laptop vs 2ο PC

Προδιεργασία / POC. Δεν είναι ακόμα production deploy guide.

## Ποιος τρέχει τι

| Μηχάνημα | Services | Ports (προτεινόμενα) |
|----------|----------|----------------------|
| **2ο PC** | Dify (όλα τα docker containers) | `80` / `443` → UI + `/v1/chat-messages` |
| **Laptop** | SCS + Qdrant | `8010`, `6333` |
| **Laptop** | dify-openai-adapter | `8085` |
| **Laptop** | OpenWebUI | `3000` |

```
OpenWebUI (laptop :3000)
  → adapter (laptop :8085)   OpenAI /v1/*
    → Dify (2ο PC)           /v1/chat-messages
      → Agents + Skills
      → External Knowledge → SCS (laptop :8010)/retrieval
```

## Laptop — adapter

```bash
cd ~/Desktop/AI-Engineering/Dify/dify-openai-adapter
cp .env.example .env
cp agents.json.example agents.json
# agents.json → πραγματικά app-… keys
# .env → DIFY_BASE_URL=http://<LAN_IP_2ΟΥ_PC>/v1

uv sync
uv run uvicorn dify_openai_adapter.main:app --app-dir src --host 0.0.0.0 --port 8085
```

OpenWebUI connection:
- API Base URL: `http://127.0.0.1:8085/v1`
- API Key: οποιοδήποτε dummy (π.χ. `sk-adapter`) — το πραγματικό key είναι ανά model στο `agents.json`

## Laptop — SCS (External Knowledge για Dify)

```bash
cd ~/Desktop/AI-Engineering/Semantic-Codebase-Search
# DIFY_EXTERNAL_API_KEY στο .env
make scs   # :8010
```

Στο Dify (2ο PC) External Knowledge endpoint πρέπει να φτάνει στο laptop:
- ίδιο LAN: `http://<LAN_IP_LAPTOP>:8010`
- ή προσωρινό tunnel όταν χρειαστεί remote test

Knowledge ID: `all` (ή project slug).  
API key: τιμή του `DIFY_EXTERNAL_API_KEY`.

## 2ο PC — Dify

- Σήκωσε το επίσημο docker compose του Dify.
- Δημοσίευσε Agents · κράτα `app-…` keys.
- Βάλε τα keys στο laptop `agents.json`.
- Model provider (π.χ. DeepSeek) στο Dify Integrations.

Δεν χρειάζεται OpenAI-compatible `/v1/models` από το ίδιο το Dify — αυτό το κάνει ο adapter.

## Έλεγχοι

```bash
# adapter
curl -s http://127.0.0.1:8085/health
curl -s http://127.0.0.1:8085/v1/models

# SCS (από laptop ή από 2ο PC στο LAN)
curl -sS http://127.0.0.1:8010/retrieval \
  -H "Authorization: Bearer $DIFY_EXTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"knowledge_id":"all","query":"test","retrieval_setting":{"top_k":2,"score_threshold":0.0}}'

# full path (όταν Dify + key είναι έτοιμα)
curl -s http://127.0.0.1:8085/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"marketing-agent","messages":[{"role":"user","content":"γεια"}]}'
```

## Αργότερα

1. Smoke test (Βήμα 5) με real `app-…` key.
2. OpenWebUI → adapter.
3. Deploy guide για VPS (μόνιμα URLs, χωρίς ad-hoc nginx guesswork).
4. Port-forward μόνο όταν ο Fotis θέλει να τεστάρει το local stack από έξω.
