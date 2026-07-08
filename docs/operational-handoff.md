# Operational handoff

Use the repository root as the canonical workspace for current Civi work.

## Local operator commands

```powershell
.\scripts\verify.ps1
docker compose --env-file .\.env -f .\infra\docker-compose.local.yml config --quiet
.\scripts\smoke-compose.ps1 -EnvFile .\.env
```

`.env` is the local runtime/deploy env file for provider-backed testing and deployment preparation. It is ignored by git and must not be committed.

For replacing an existing service on the same host, choose `CHANNEL_GATEWAY_PORT` intentionally and confirm the old service has been stopped before starting the new compose stack.

`runt-service` and `simit-service` use the browser-ready Dockerfile so `RUNT_PROVIDER_MODE=browser` and `SIMIT_PROVIDER_MODE=browser` can run without the old runtime tree.

## Deployment preparation only

```powershell
.\scripts\verify-deploy-config.ps1 -EnvFile .\.env
docker compose --env-file .\.env -f .\infra\docker-compose.deploy.yml config --quiet
```

Do not commit `.env`. Do not deploy from this handoff step.
