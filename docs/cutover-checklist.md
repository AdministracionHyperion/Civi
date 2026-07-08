# Civi local readiness checklist

This checklist defines the evidence required before treating this workspace as functionally ready for local operation.

## Required gates

```powershell
.\scripts\verify.ps1
docker compose -f .\infra\docker-compose.local.yml config --quiet
.\scripts\smoke-compose.ps1
```

## What must be proven

- no committed real `.env` files, logs, tunnels, dumps, `node_modules`, `.venv`, scratch or backup folders;
- high-confidence secret scan passes;
- local providers default to disabled;
- event publishing defaults to disabled locally;
- workers expose no public ports;
- each Python service compiles;
- service boundary verification blocks runtime imports across services;
- SQL ownership verification passes for stateful services;
- OpenAPI contracts match FastAPI runtime routes;
- all Python and Node tests pass;
- local compose defines every runtime service and worker;
- Docker smoke proves all service health endpoints and worker containers.

## Product flows to cover

- consent pending and accepted;
- SOAT/RTM validity through `vehicle-service` and `runt-service`;
- SIMIT fines through `vehicle-service` and `simit-service`;
- partner lookup and appointment creation;
- reminders and notification outbox;
- audio and image processing;
- deterministic domain knowledge;
- reference quotes;
- payment intent preparation;
- human handoff;
- admin operational status and audit.

## Local service topology

The local stack includes:

```text
channel-gateway
conversation-service
bot-orchestrator
vehicle-service
runt-service
simit-service
places-service
appointment-service
notification-service
notification-worker
media-service
knowledge-service
quote-service
billing-service
handoff-service
admin-service
admin-event-audit-worker
postgres
redis
```
