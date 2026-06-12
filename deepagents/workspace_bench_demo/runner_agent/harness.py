"""Agent harness for workspace-bench tasks.

Builds and returns a deepagents LangGraph agent with:
- ChatOpenAI LLM (deepseek-v4-pro)
- LocalShellBackend for filesystem access
- Custom tools (parse_pdf, compute_hash)
- System prompt loaded from prompt.txt
"""

import logging
import os
import sys
import time
from pathlib import Path

import httpx
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from runner_agent.tools import compute_hash, parse_pdf

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().with_suffix("").parent / "prompt.txt"


def _load_prompt() -> str:
    """Load the system prompt from prompt.txt."""
    if not _PROMPT_PATH.exists():
        raise FileNotFoundError(f"Prompt file not found: {_PROMPT_PATH}")
    return _PROMPT_PATH.read_text(encoding="utf-8")


class _RetryTransport(httpx.BaseTransport):
    """HTTP transport wrapper that retries on transient connection errors.

    Catches RemoteProtocolError and other connection drops that commonly
    occur with streaming LLM APIs, and retries with exponential backoff.
    """

    def __init__(
        self,
        transport: httpx.BaseTransport,
        max_retries: int = 3,
        backoff_base: float = 1.0,
    ):
        self._transport = transport
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                return self._transport.handle_request(request)
            except httpx.RemoteProtocolError as e:
                last_exc = e
                if attempt < self._max_retries:
                    wait = self._backoff_base * (2 ** attempt)
                    logger.warning(
                        "RemoteProtocolError on attempt %d/%d, retrying in %.1fs: %s",
                        attempt + 1,
                        self._max_retries + 1,
                        wait,
                        e,
                    )
                    time.sleep(wait)
                else:
                    raise
            except (httpx.ConnectError, httpx.ReadError) as e:
                last_exc = e
                if attempt < self._max_retries:
                    wait = self._backoff_base * (2 ** attempt)
                    logger.warning(
                        "HTTP error on attempt %d/%d, retrying in %.1fs: %s",
                        attempt + 1,
                        self._max_retries + 1,
                        wait,
                        e,
                    )
                    time.sleep(wait)
                else:
                    raise
        # Should not reach here, but if we do, re-raise
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("_RetryTransport: unexpected state — no response and no exception")

    def close(self) -> None:
        self._transport.close()


def build_agent(model: str | None = None, read_timeout: float = 30.0):
    """Build and return the agent for workspace-bench tasks.

    The work directory is read from WB_TASK_WORK_DIR env var, falling back to cwd.
    The model defaults to INNER_AGENT_MODEL env var, then "deepseek-v4-pro".

    Args:
        model: Model name override. Defaults to INNER_AGENT_MODEL env var.
        read_timeout: HTTP read timeout in seconds. Defaults to 30.0.
            The outer retry loop in runner_agent.core will double this on each retry.
    """
    model = model or os.getenv("INNER_AGENT_MODEL", "deepseek-v4-pro")
    work_dir = os.environ.get("WB_TASK_WORK_DIR", os.getcwd())
    logger.info("Building agent with work_dir=%s model=%s read_timeout=%s", work_dir, model, read_timeout)
    logger.info(
        "[build_agent] python=%s version=%s prefix=%s",
        sys.executable,
        sys.version.replace("\n", " "),
        getattr(sys, "prefix", "unknown"),
    )

    # Ensure execute() uses the same venv Python, not system Python
    if hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix:
        venv_bin = os.path.join(sys.prefix, "bin")
        if os.path.isdir(venv_bin):
            current_path = os.environ.get("PATH", "")
            if venv_bin not in current_path:
                os.environ["PATH"] = f"{venv_bin}:{current_path}"
                logger.info("Prepended venv bin to PATH: %s", venv_bin)

    backend = None
    try:
        from deepagents.backends import LocalShellBackend

        backend = LocalShellBackend(
            root_dir=work_dir,
            virtual_mode=False,
            inherit_env=True,
            timeout=60,
        )
    except ImportError:
        logger.warning("LocalShellBackend not available, falling back to default backend")

    # Wrap default transport with retry logic to handle transient connection
    # drops (RemoteProtocolError) that occur with streaming LLM APIs.
    base_transport = httpx.HTTPTransport(http2=False)
    retry_transport = _RetryTransport(
        transport=base_transport,
        max_retries=3,
        backoff_base=1.0,
    )
    _http_client = httpx.Client(transport=retry_transport, http2=False)

    llm = ChatOpenAI(
        model=model,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        timeout=httpx.Timeout(
            connect=30.0,
            read=read_timeout,
            write=30.0,
            pool=10.0,
        ),
        max_retries=0,  # Retries are handled by _RetryTransport at the HTTP level
        streaming=True,
        extra_body={"thinking": {"type": "disabled"}},
        http_client=_http_client,
    )

    return create_deep_agent(
        model=llm,
        backend=backend,
        system_prompt=_load_prompt(),
        tools=[parse_pdf, compute_hash],
    )