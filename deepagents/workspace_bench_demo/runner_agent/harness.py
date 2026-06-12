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

    # Docker 内 Moonshot API HTTP/2 SSL 握手失败，强制禁用 HTTP/2
    _http_client = httpx.Client(http2=False)

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
        max_retries=0,  # Outer retry loop in runner_agent.core handles retries
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