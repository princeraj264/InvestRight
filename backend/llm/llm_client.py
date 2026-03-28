"""
Central wrapper for all Anthropic API calls.
All LLM agents use this — never call the Anthropic API directly.

Design rules:
  - Returns None on ANY failure (never raises).
  - ANTHROPIC_API_KEY missing → log critical once, return None.
  - 30-second timeout per call.
  - No retries — let the caller's fallback handle it.
  - Logs every call to llm_calls table via audit_log.
"""
import os
import time
import logging
from typing import Optional

_logger = logging.getLogger("llm_client")
_api_key_missing_logged = False

# Token limit safety buffer — truncate prompt if it would exceed this
_MAX_PROMPT_CHARS = 12000   # rough guard (~3000 tokens at 4 chars/token)


def call_llm(
    prompt: str,
    system: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 1000,
    trace_id: Optional[str] = None,
    agent_name: str = "unknown",
) -> Optional[str]:
    """
    Call the Anthropic API and return the response text.

    Args:
        prompt:     User-role message content.
        system:     System-role prompt.
        model:      Model ID (defaults to Haiku for speed/cost).
        max_tokens: Maximum tokens in the response.
        trace_id:   Pipeline trace UUID for audit logging.
        agent_name: Caller name for the llm_calls log.

    Returns:
        Response text string, or None on any failure.
    """
    global _api_key_missing_logged

    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        if not _api_key_missing_logged:
            _logger.critical(
                "[LLM_CLIENT] ANTHROPIC_API_KEY not set — LLM features disabled. "
                "All agents will use fallbacks."
            )
            _api_key_missing_logged = True
        return None

    # Truncate over-long prompts (preserve first 60% + last 40%)
    if len(prompt) > _MAX_PROMPT_CHARS:
        keep_start = int(_MAX_PROMPT_CHARS * 0.6)
        keep_end   = _MAX_PROMPT_CHARS - keep_start
        truncated  = prompt[:keep_start] + "\n[...truncated...]\n" + prompt[-keep_end:]
        _logger.warning(
            f"[LLM_CLIENT] Prompt truncated from {len(prompt)} to {_MAX_PROMPT_CHARS} chars"
        )
        prompt = truncated

    start_ms = int(time.monotonic() * 1000)
    status   = "failure"
    prompt_tokens     = None
    completion_tokens = None
    response_text     = None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key, timeout=30.0)

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        if response.content and len(response.content) > 0:
            raw = response.content[0]
            response_text = getattr(raw, "text", None)

        if response_text:
            status = "success"

        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens     = getattr(usage, "input_tokens",  None)
            completion_tokens = getattr(usage, "output_tokens", None)

    except Exception as e:
        _logger.warning(f"[LLM_CLIENT] API call failed ({agent_name}): {e}")

    latency_ms = int(time.monotonic() * 1000) - start_ms

    # Log to llm_calls table (fire-and-forget)
    _log_llm_call(
        trace_id=trace_id,
        agent=agent_name,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        status=status,
    )

    return response_text


def _log_llm_call(
    trace_id: Optional[str],
    agent: str,
    model: str,
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    latency_ms: int,
    status: str,
) -> None:
    """Insert a row into llm_calls (best-effort, non-blocking)."""
    import threading

    def _write():
        try:
            from db.connection import db_cursor
            with db_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO llm_calls
                        (trace_id, agent, model, prompt_tokens,
                         completion_tokens, latency_ms, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (trace_id, agent, model, prompt_tokens,
                     completion_tokens, latency_ms, status),
                )
        except Exception:
            pass  # Never crash for logging

    threading.Thread(target=_write, daemon=True).start()
