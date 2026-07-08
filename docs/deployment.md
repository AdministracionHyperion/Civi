# Deployment configuration

This document explains deploy preparation only. It does not perform deployment.

## API mapping

| Capability | Owner | Configuration |
| --- | --- | --- |
| LLM fallback | `bot-orchestrator` | `LLM_PROVIDER_MODE=openai|deepseek|groq` |
| WhatsApp inbound | `channel-gateway` | `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` |
| WhatsApp outbound | `notification-service` | `WHATSAPP_PROVIDER_MODE=meta` |
| Audio transcription | `media-service` | `MEDIA_AUDIO_PROVIDER_MODE=openai` |
| Image extraction | `media-service` | `MEDIA_IMAGE_PROVIDER_MODE=openai|deepseek|groq` |
| RUNT | `runt-service` through `vehicle-service` | `RUNT_PROVIDER_MODE=http|browser`, `RUNT_PROVIDER_API_URL` for HTTP or `CAPTCHA_API_KEY` for browser |
| RUNT person profile | `runt-service` through `vehicle-service` | `RUNT_PERSONA_PROVIDER_MODE=http`, `RUNT_PERSONA_PROVIDER_API_URL` |
| SIMIT | `simit-service` through `vehicle-service` | `SIMIT_PROVIDER_MODE=http|browser`, `SIMIT_PROVIDER_API_URL` for HTTP |
| Domain knowledge | `knowledge-service` | internal service URL |
| Quotes | `quote-service` | internal service URL |
| Billing | `billing-service` | internal service URL |
| Human handoff | `handoff-service` | internal service URL |

## Prepare an env file

The deploy/runtime env for a local checkout should be stored in `.env`.
It is intentionally ignored by git. Do not commit it.

```powershell
.\scripts\verify-deploy-config.ps1 -EnvFile .\.env
```

The verifier fails if required values are missing or placeholders remain.

`WHATSAPP_APP_SECRET` must come from Meta App Dashboard -> Settings -> Basic. It is not the same as `WHATSAPP_VERIFY_TOKEN`. Keep `WHATSAPP_SIGNATURE_REQUIRED=true` for production unless a controlled compatibility window explicitly requires otherwise.

For same-host replacement deployments, choose `CHANNEL_GATEWAY_PORT` to avoid conflicts with existing services. During cutover, stop the old public bot service before starting the new compose stack so only one process owns the public bot port.

For local provider testing, pass the same env file:

```powershell
docker compose --env-file .\.env -f .\infra\docker-compose.local.yml up --build
```

## Validate compose

```powershell
docker compose --env-file .\.env -f .\infra\docker-compose.deploy.yml config --quiet
```

Real deploy execution is intentionally separate from this workspace validation.
