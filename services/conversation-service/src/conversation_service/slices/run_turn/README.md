# run_turn slice

Coordinates one user turn:

1. Load conversation state.
2. Call `bot-orchestrator`.
3. Persist state changes and final history.
4. Return a channel reply to `channel-gateway`.
