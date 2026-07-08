# Civi clean product blueprint

## Decision

Civi is a clean microservices product. The repository contains only current runtime code, current contracts, current tests and current operations material.

The previous implementation is treated as an external requirements source. It is not part of this product tree, runtime, test path, compose topology or package graph.

## Runtime services

```text
channel-gateway        public ingress for WhatsApp, web chat and admin channels
conversation-service   consent, user/session state and conversation history
bot-orchestrator       intent routing, tool planning, prompts, policies and response validation
vehicle-service        vehicle domain facade for SOAT, RTM, driver profile and fines
runt-service           clean RUNT adapter and normalization boundary
simit-service          clean SIMIT adapter and normalization boundary
places-service         CDA, CRC, CEA, CIA, partners, coverage and geocoding
appointment-service    appointments, partner confirmation and cancellation
notification-service   outbound WhatsApp, reminders and outbox
media-service          audio/image validation, transcription and extraction
knowledge-service      deterministic tecnomecanica, CIA and city coverage knowledge
quote-service          service, insurance and inspection reference quotes
billing-service        payment intents and receipts
handoff-service        human escalation queue
admin-service          dashboard, audit and operational status
```

## Service rules

- Each service owns its own slice code, contract and data boundary.
- Services integrate through internal HTTP contracts or events.
- No service imports another service package at runtime.
- External providers are always behind outbound adapters and env-gated modes.
- Local defaults are safe: no provider calls, no public worker ports and no real secrets.

## Bot rules

The bot is not a single prompt. `bot-orchestrator` is built from:

- prompt parts for identity, tone, business rules, safety and flow policy;
- deterministic intent routing for known product flows;
- entity extraction for plate, document, city, date, service and channel;
- tool planning against internal services;
- deterministic knowledge lookup before LLM fallback;
- policy checks for consent, PII, no fabrication and escalation;
- response composition and validation before sending text to the user;
- golden conversation tests for product behavior.

## Clean product invariant

The repository must not contain retired runtime trees, bridge files, copied old bot packages or source imports from the previous implementation. If such names reappear in active source, verification must fail.
