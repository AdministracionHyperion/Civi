# Bot orchestrator blueprint

## Internal structure

```text
bot-orchestrator/
  prompts/
  adapters/outbound/
  slices/run_turn/
    extractors.py
    formatters.py
    use_case.py
    schemas.py
  policies/
  evaluations/
```

## Turn sequence

1. `channel-gateway` normalizes public input.
2. `conversation-service` enforces consent before the bot sees the message.
3. `bot-orchestrator` classifies intent and extracts entities.
4. Known flows use internal tools before any LLM fallback.
5. Unknown flows may use the configured LLM provider if explicitly enabled.
6. Responses are short, factual and formatted for WhatsApp.

## Current tools

- `appointment.list`
- `places.find_nearest`
- `appointment.select_place`
- `appointment.create`
- `appointment.cancel`
- `notification.schedule`
- `knowledge.get_info`
- `knowledge.city_info`
- `vehicle.check_vigencia`
- `vehicle.consult_multas`
- `quote.create`
- `billing.payment_intent.create`
- `handoff.create`
- `llm.complete`

## Response policy

- Do not invent RUNT, SIMIT, domain knowledge, payment, appointment or quote results.
- Ask for missing plate, document, city, procedure or date instead of guessing.
- Use valid Colombia GPS metadata for center search before asking for city.
- When a known appointment procedure is missing location, keep a pending context and resume after a city or WhatsApp pin arrives.
- If multiple centers are available, ask the user to choose one before creating the appointment.
- Use a human handoff when the user explicitly asks for a person or the flow is outside supported scope.
- Keep provider details, secrets, full document numbers and raw event ids out of user-facing responses.
