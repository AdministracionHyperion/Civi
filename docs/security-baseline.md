# Security baseline

## Local defaults

- Provider modes default to `disabled`.
- Event publishing defaults to `disabled`.
- CORS is closed unless `CHANNEL_CORS_ALLOWED_ORIGINS` is set.
- Workers expose no public ports.
- Real secrets must not be committed.

## Provider boundaries

- `bot-orchestrator` may call OpenAI, DeepSeek or Groq only when explicitly configured.
- `media-service` may call OpenAI/DeepSeek/Groq only when explicitly configured.
- `notification-service` may call Meta WhatsApp only when explicitly configured.
- `billing-service` currently creates local payment intents without a payment provider.
- `runt-service` and `simit-service` are internal-only normalization boundaries.

## Privacy

- Consent is enforced by `conversation-service` before bot execution.
- User-facing responses must not include full document numbers, provider message ids or internal event ids.
- Admin event audit stores operational metadata, not raw user text.

## Required checks

```powershell
.\scripts\verify-secrets.ps1
python .\scripts\verify-config-defaults.py
python .\scripts\verify-service-boundaries.py
```
