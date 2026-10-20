# Discord ↔ Dify Hello (PoC)

## Path A — Posts via webhook (ξεκίνα από εδώ)

Δεν χρειάζεται Discord Bot. Μόνο webhook URL.

```
εσύ → post_poc.py → Dify Hello Agent → Discord webhook → post στο channel
```

1. Στο Discord channel: **Edit Channel → Integrations → Webhooks → New Webhook → Copy Webhook URL**
2. Βάλε το στο `.env` ως `DISCORD_WEBHOOK_URL=...`
3. Τρέξε:

```bash
cd discord-dify-poc
source .venv/bin/activate
python post_poc.py "Γεια σου, ποιος είσαι;"
```

Θα εμφανιστεί post στο channel με ερώτηση + απάντηση Agent.

## Path B — Interactive bot (αργότερα)

Χρειάζεται Bot Token από Developer Portal (δεν γίνεται μόνο με webhook).

```
Discord @mention → bot.py → Dify Hello → reply στο channel
```

```bash
# put DISCORD_TOKEN in .env
python bot.py
```

## Agent details (μετά το deploy)

| Field | Value |
|-------|-------|
| Name | Dify Hello / Emblem agent (ό,τι δημοσιευτεί στο live Dify) |
| Type | Agents — not Web App |
| Mode | `agent` |
| API key | `app-…` από το live Dify μετά το publish (όχι localhost key) |
| API | `POST {DIFY_BASE_URL}/chat-messages` (streaming) |
