"""Optional Langfuse tracing for the agent graphs.

Tracing is on only when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set and the
`langfuse` package is installed. Otherwise every helper returns the config it was given
and the app behaves exactly as without tracing: no import, no network call, no error.
"""
import logging
import os

from langchain_core.callbacks import CallbackManager

logger = logging.getLogger(__name__)


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def _callback_handler():
    from langfuse.langchain import CallbackHandler  # lazy: only imported when tracing is enabled

    return CallbackHandler()


def tracing_config(name: str, user_id: str | None = None, session_id: str | None = None,
                   base: dict | None = None) -> dict:
    """Return a LangGraph config with the Langfuse callback when tracing is enabled,
    otherwise `base` unchanged. Never raises."""
    config = dict(base or {})
    if not tracing_enabled():
        return config
    try:
        handler = _callback_handler()
    except Exception:
        logger.warning("Langfuse tracing is configured but not available; running without it", exc_info=True)
        return config

    metadata = {**(config.get("metadata") or {}), "langfuse_trace_name": name, "langfuse_tags": [name]}
    if user_id:
        metadata["langfuse_user_id"] = str(user_id)
    if session_id:
        metadata["langfuse_session_id"] = str(session_id)
    return {
        **config,  # keeps configurable.thread_id of the chat and the explain agent
        "callbacks": [*(config.get("callbacks") or []), handler],
        "run_name": name,
        "metadata": metadata,
    }


def child_config(parent: dict | None, **extra) -> dict:
    """Config for a graph run inside a node, so it appears inside the parent trace.

    Only the Langfuse handler is passed down (still attached to the parent run). The other
    parent callbacks, e.g. the one LangGraph uses to stream tokens to the chat, are left
    out so an inner model's raw output is never streamed to the student."""
    manager = (parent or {}).get("callbacks")
    if not tracing_enabled() or not isinstance(manager, CallbackManager):
        return dict(extra)

    def tracing_only(handlers):
        return [h for h in handlers if type(h).__module__.startswith("langfuse")]

    handlers = tracing_only(manager.handlers)
    if not handlers:
        return dict(extra)
    inheritable = tracing_only(manager.inheritable_handlers)
    return {
        **extra,
        "callbacks": CallbackManager(handlers, inheritable, parent_run_id=manager.parent_run_id),
    }


def flush_tracing() -> None:
    """Send pending traces (e.g. from insights background tasks) before the backend stops."""
    if not tracing_enabled():
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        logger.warning("Could not flush Langfuse traces", exc_info=True)
