# Security

- Never commit `.env` or API keys.
- Open demo: no login. Rate-limit analyze/chat/eval endpoints.
- Rate-limit analyze/chat endpoints.
- `max_agent_steps`, timeout, and `MAX_OUTPUT_TOKENS` are hard limits.
- LLM keys are server-side only.
- Do not log raw secrets, cookie values, or full prompts in frontend telemetry.
