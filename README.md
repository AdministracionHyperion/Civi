# Civi

Civi is a clean microservices product for vehicle services, appointments, WhatsApp operations, media processing, deterministic knowledge, quotes, billing and human escalation.

## Runtime services

- `services/channel-gateway`: public ingress for WhatsApp, WhatsApp location pins and web chat.
- `services/conversation-service`: consent, conversation state and history.
- `services/bot-orchestrator`: intent routing, prompt policy, GPS-aware appointment routing, tools and response validation.
- `services/vehicle-service`: vehicle domain facade for SOAT, RTM, profile and fines.
- `services/runt-service`: clean RUNT boundary.
- `services/simit-service`: clean SIMIT boundary.
- `services/places-service`: partner centers, geocoding and coverage.
- `services/appointment-service`: appointment lifecycle.
- `services/notification-service`: WhatsApp outbound, reminders and outbox.
- `services/media-service`: audio and image processing.
- `services/knowledge-service`: deterministic tecnomecanica, CIA and coverage knowledge.
- `services/quote-service`: reference quotes for Civi services.
- `services/billing-service`: payment intent boundary.
- `services/handoff-service`: human escalation queue.
- `services/admin-service`: dashboard, audit and operational status.

## Important docs

- `docs/clean-product-blueprint.md`: clean runtime architecture.
- `docs/product-parity.md`: product capability matrix.
- `docs/bot-orchestrator-flow.md`: bot flow and tool policy.
- `docs/bot-design/bot-orchestrator-blueprint.md`: bot internals.
- `docs/security-baseline.md`: local safety and provider rules.
- `docs/deployment.md`: deploy configuration without committing secrets.

## Local verification

```powershell
.\scripts\verify.ps1
docker compose -f .\infra\docker-compose.local.yml config --quiet
.\scripts\smoke-compose.ps1
```

`scripts/verify.ps1` checks secrets, safe defaults, deploy config template, service boundaries, data ownership, OpenAPI/runtime parity and all tests.

## Deploy preparation

No deployment is performed by verification. Runtime credentials for this checkout live in the ignored local file `.env` at the project root. To validate deployment configuration:

```powershell
.\scripts\verify-deploy-config.ps1 -EnvFile .\.env
docker compose --env-file .\.env -f .\infra\docker-compose.deploy.yml config --quiet
```

Do not commit `.env`.
