# Setup @AIAssistant Bot (απαιτείται για ερωτήσεις από Discord)

Το webhook **μόνο στέλνει** posts. Για να διαβάζει ερωτήσεις και να απαντάει μέσα σε Forum post → **Discord Bot**.

## 1. Δημιούργησε Application

1. Άνοιξε https://discord.com/developers/applications
2. **New Application** → όνομα: `AIAssistant`
3. Αριστερά **Bot** → **Add Bot**
4. **Username**: `AIAssistant` (έτσι θα φαίνεται το `@AIAssistant`)
5. **Reset Token** → Copy → βάλε στο `.env` ως `DISCORD_TOKEN=...`
6. **Privileged Gateway Intents** → άνοιξε **MESSAGE CONTENT INTENT** → Save

## 2. Invite στο TechFlowLabs

1. **OAuth2 → URL Generator**
2. Scopes: `bot`
3. Bot Permissions:
   - View Channels
   - Send Messages
   - Send Messages in Threads
   - Read Message History
   - Mention Everyone **όχι** (δεν χρειάζεται)
4. Άνοιξε το generated URL → πρόσθεσε το bot στο server

## 3. Forum channel id (προαιρετικό αλλά καλό)

Στο Discord: δεξί κλικ στο `#ai-assistant` → Copy Channel ID  
(Χρειάζεται Developer Mode: User Settings → Advanced → Developer Mode)

Στο `.env`:
```
POC_CHANNEL_ID=το-forum-channel-id
```

## 4. Τρέξε

```bash
cd discord-dify-poc
source .venv/bin/activate
# DISCORD_TOKEN=... στο .env
python bot.py
```

## 5. Χρήση

Μέσα σε ένα Forum post στο `#ai-assistant`:

```
@AIAssistant Μπορείς να απαντήσεις και σε εμένα δηλαδή;
```

Ο καθένας στο ίδιο post μπορεί να ξαναρωτήσει με `@AIAssistant` — η συζήτηση συνεχίζεται στο ίδιο thread.
