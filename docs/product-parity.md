# Product parity matrix

This matrix defines the product surface that must remain available while the codebase stays clean and service-oriented.

| Product capability | Current owner | Runtime state | Acceptance evidence |
| --- | --- | --- | --- |
| WhatsApp inbound | `channel-gateway` | Implemented, including text and valid Colombia location pins | Webhook tests, signature policy, local smoke |
| Consent and conversation state | `conversation-service` | Implemented | Consent tests, history tests, offline core flow |
| Bot routing and responses | `bot-orchestrator` | Implemented and expanding | Golden conversations, no-fabrication tests |
| SOAT/RTM validity | `vehicle-service` + `runt-service` | Implemented locally, HTTP-gated and browser-gated | Vehicle tests, RUNT service tests, HTTP provider tests, browser parser tests, bot tool call tests |
| RUNT person profile | `vehicle-service` + `runt-service` | Implemented, HTTP-gated | RUNT persona provider tests, vehicle tests, bot tool call tests |
| SIMIT fines | `vehicle-service` + `simit-service` | Implemented locally, HTTP-gated and browser-gated | Vehicle tests, SIMIT service tests, HTTP provider tests, browser parser tests, bot tool call tests |
| Partner and center lookup | `places-service` | Implemented with city fallback and GPS distance ranking | Places tests and appointment flow |
| Appointments | `appointment-service` | Implemented with pending location resume and explicit center selection before scheduling | Create/list/cancel tests and offline flow |
| Outbound WhatsApp and reminders | `notification-service` | Implemented, provider-gated | Provider mock tests, worker tests |
| Media processing | `media-service` | Implemented, provider-gated | Audio/image tests |
| Deterministic domain knowledge | `knowledge-service` | Implemented with legacy-style tecnomecanica, CIA and city coverage topics | Knowledge service tests, bot knowledge flow |
| Reference quotes | `quote-service` | Implemented locally with legacy-style exact SOAT, tecnomecanica, CIA course and CNT infraction quotes when inputs are available | Quote service tests, bot quote flow |
| Payment intents | `billing-service` | Implemented locally, provider-gated | Billing service tests, bot payment flow |
| Human handoff | `handoff-service` | Implemented locally | Handoff service tests, bot handoff flow |
| Admin dashboard and audit | `admin-service` | Implemented | Admin tests, event audit worker tests |

## Product-level acceptance

The product is considered functionally ready for local operation when:

1. `scripts/verify.ps1` passes.
2. `docker compose -f infra/docker-compose.local.yml config --quiet` passes.
3. `scripts/smoke-compose.ps1` passes when Docker Desktop is available.
4. Golden conversations cover SOAT, RTM, SIMIT, appointment, places, quote, knowledge, payment, media and handoff flows.
5. No retired runtime tree or bridge file exists in the repo.
6. Production-like env files set `RUNT_PROVIDER_MODE=http|browser` and `SIMIT_PROVIDER_MODE=http|browser` before external vehicle data is considered real.
