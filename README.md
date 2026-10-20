# Dify + Discord — deploy package

Πακέτο για deploy στο Emblem server. **Δεν** περιλαμβάνει τοπικά volumes, πραγματικά `.env`, ούτε `app-…` keys.

## Setup (χωρίς secrets στο git)

```bash
cp discord-dify-poc/.env.example discord-dify-poc/.env
# optional OpenWebUI:
cp dify-openai-adapter/.env.example dify-openai-adapter/.env
cp dify-openai-adapter/agents.json.example dify-openai-adapter/agents.json
```

Δες και το root `.env.example` για checklist. Τα `.env` / `agents.json` είναι στο `.gitignore`.

## Τι υπάρχει εδώ

| Φάκελος | Χρήση |
| --- | --- |
| `discord-dify-poc/` | Discord bot / webhook προς Dify `/v1` |
| `dify-openai-adapter/` | Προαιρετικό — OpenWebUI → Dify |

## Τι ζητάμε να γίνει deploy

1. **Dify** — καθαρό official docker compose (όχι το laptop project με volumes).
2. **SCS + Qdrant** — αν θέλουμε RAG από την πρώτη μέρα (External Knowledge από Dify προς SCS `/retrieval`).
3. **Discord bot** — από το `discord-dify-poc`, με `DIFY_BASE_URL` στο deployed Dify.

OpenWebUI + adapter **δεν** είναι απαραίτητα για Discord.

## Τι να μας δώσεις μόλις είναι up

- URL Dify (UI + API, π.χ. `https://…/v1`)
- Admin login (ή ισοδύναμο access)
- Επιβεβαίωση ότι το Dify φτάνει το SCS (αν ανέβει και το SCS)

Μετά το up: στήνουμε/δημοσιεύουμε agent, External Knowledge, και βάζουμε το νέο `app-…` στο Discord bot `.env`.

## Τι να ΜΗΝ περιμένεις σε αυτό το zip

- Ολόκληρο τοπικό Dify + Postgres volumes
- Knowledge/Qdrant data
- Secrets / Discord token / API keys
- Rules-tags GitHub Action (τοπικό POC· μετά το host)

## Γρήγορο check μετά το Dify up

```bash
curl -sS "$DIFY_BASE_URL/../health" || true
# Discord PoC (αφού μπουν secrets στο .env):
# cd discord-dify-poc && python post_poc.py "γεια"
```
