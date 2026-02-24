"""
agent-observe-sdk — lightweight telemetry for agent observability.

Usage:
    from agent_observe_sdk import Observer

    observer = Observer(api_key="ak_spend_...")

    @observer.track
    def my_agent(query: str) -> dict:
        return {"sql": "SELECT ...", "status": "success"}
"""

import re
import time
import threading
import functools
from typing import Optional, Callable

try:
    import requests
except ImportError:
    requests = None

SQL_KEYWORDS_RE = re.compile(
    r'\b(SELECT\s.+\sFROM|INSERT\s+INTO|UPDATE\s.+\sSET|DELETE\s+FROM|WITH\s.+\sAS)\b',
    re.IGNORECASE,
)

SQL_FIELD_NAMES = {"sql", "generated_sql", "sql_query", "response_sql", "query_sql"}


class Observer:
    """
    Observability observer for AI agents.

    Captures input, output, latency, and errors — sends telemetry
    asynchronously to the observability platform. Fire-and-forget:
    if the platform is unreachable, the agent is unaffected.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str = "http://localhost:8000",
        enabled: bool = True,
    ):
        try:
            self.api_key = api_key
            self.endpoint = endpoint.rstrip("/")
            self.enabled = enabled
            self._ingest_url = f"{self.endpoint}/api/v1/monitor/ingest/sdk"
        except Exception:
            self.enabled = False

    def track(self, fn: Optional[Callable] = None, *, query_param: str = "query"):
        """
        Decorator that wraps an agent function to capture telemetry.

        @observer.track
        def my_agent(query: str) -> dict:
            return {"sql": "SELECT ...", "status": "success"}

        @observer.track(query_param="question")
        def my_agent(question: str) -> dict:
            ...
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                query_text = kwargs.get(query_param) or (args[0] if args else "unknown")

                start = time.time()
                error_msg = None
                result = None
                status = "success"

                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e)
                    status = "error"
                    raise
                finally:
                    try:
                        elapsed_ms = (time.time() - start) * 1000

                        detected_sql = _extract_sql(result)
                        if isinstance(result, dict):
                            status = result.get("status", status)
                            error_msg = result.get("error", error_msg)

                        if self.enabled:
                            self._send_async(
                                query_text=str(query_text),
                                sql=detected_sql,
                                status=status,
                                error=error_msg,
                                execution_time_ms=elapsed_ms,
                            )
                    except Exception:
                        pass  # Telemetry failure must never affect the agent

                return result
            return wrapper

        if fn is not None:
            return decorator(fn)
        return decorator

    def wrap(self, fn: Callable, query_param: str = "query") -> Callable:
        """
        Wrap an existing function with telemetry tracking.

            agent.process_query = observer.wrap(agent.process_query)
        """
        return self.track(fn, query_param=query_param)

    def _send_async(self, query_text, sql, status, error, execution_time_ms):
        """Fire-and-forget telemetry send in a daemon thread."""
        thread = threading.Thread(
            target=self._send,
            args=(query_text, sql, status, error, execution_time_ms),
            daemon=True,
        )
        thread.start()

    def _send(self, query_text, sql, status, error, execution_time_ms):
        """Send telemetry to the observability platform. Never raises."""
        if requests is None:
            return
        try:
            payload = {
                "query_text": query_text,
                "agent_type": "sdk",
                "status": status,
                "sql": sql,
                "error": error,
                "execution_time_ms": execution_time_ms,
            }
            requests.post(
                self._ingest_url,
                json=payload,
                headers={"X-API-Key": self.api_key},
                timeout=5,
            )
        except Exception:
            pass  # Fire-and-forget: agent must never be affected


def _extract_sql(result) -> Optional[str]:
    """Auto-detect SQL from a function's return value."""
    if result is None:
        return None

    if isinstance(result, str):
        return result if SQL_KEYWORDS_RE.search(result) else None

    if isinstance(result, dict):
        # Check explicit SQL field names first
        for field in SQL_FIELD_NAMES:
            if field in result and isinstance(result[field], str):
                return result[field]
        # Fallback: scan all string values for SQL patterns
        for value in result.values():
            if isinstance(value, str) and SQL_KEYWORDS_RE.search(value):
                return value

    return None
