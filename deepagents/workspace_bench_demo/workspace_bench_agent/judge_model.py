"""Judge LLM instance — similar to inner agent's ChatOpenAI setup.

Provides a LangChain ChatOpenAI model for the judge (evaluator),
with the same robust connection config (timeout, retries) as the inner agent.
"""

import base64
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI

logger = logging.getLogger(__name__)
Json = Any

# ═══════════════════════════════════════════════════════════════
# 1. Build a Judge LLM instance (like build_agent() for inner)
# ═══════════════════════════════════════════════════════════════


def build_judge_llm(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """Build and return a ChatOpenAI instance for judge (evaluator).

    Args:
        model: Model name. Defaults to JUDGE_MODEL env var, then "deepseek-v4-pro".
        api_key: API key. Defaults to JUDGE_API_KEY env var.
        base_url: API base URL. Defaults to JUDGE_BASE_URL env var, then "https://api.deepseek.com".
        temperature: Sampling temperature. 0 for deterministic evaluation.

    Returns:
        A configured ChatOpenAI instance ready for judge.invoke().
    """
    model = model or os.environ.get("JUDGE_MODEL", "deepseek-v4-pro")
    api_key = api_key or os.environ.get("JUDGE_API_KEY")
    base_url = base_url or os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        raise ValueError(
            "JUDGE_API_KEY not provided. Set it via env var or pass api_key=..."
        )

    logger.info(f"Building judge LLM: model={model}, base_url={base_url}")

    # Docker 内 HTTP/2 SSL 握手可能失败，强制禁用 HTTP/2
    _http_client = httpx.Client(http2=False)

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(
            connect=5.0,
            read=60.0,      # Judge evaluates complex rubrics; give it more time
            write=10.0,
            pool=5.0,
        ),
        max_retries=5,
        streaming=False,   # Judge doesn't need streaming
        temperature=temperature,
        extra_body={"thinking": {"type": "disabled"}},
        http_client=_http_client,
    )


# ═══════════════════════════════════════════════════════════════
# 2. Quick chat-completion helper (OpenAI-style interface)
# ═══════════════════════════════════════════════════════════════


def _extract_image_ext(url: str) -> str:
    """Extract image extension from data URI or filename."""
    if url.startswith("data:image/"):
        mime = url.split(";")[0].split("/")[1]
        return mime if mime else "png"
    return "png"


def _upload_image_to_moonshot(
    *,
    client: OpenAI,
    base64_data: str,
    ext: str,
) -> str:
    """Upload a base64 image to Moonshot and return extracted text content."""
    # Decode base64 to bytes
    image_bytes = base64.b64decode(base64_data)
    # Write to temp file
    suffix = f".{ext}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = Path(tmp.name)
    try:
        file_obj = client.files.create(file=tmp_path, purpose="file-extract")
        file_content = client.files.content(file_id=file_obj.id).text
        return file_content
    finally:
        tmp_path.unlink(missing_ok=True)


def _convert_messages_for_moonshot(
    *,
    messages: list[dict[str, Json]],
    client: OpenAI,
) -> list[dict[str, Json]]:
    """Convert OpenAI-style messages to Moonshot-compatible format.

    Replaces image_url blocks with extracted text via Moonshot file API.
    """
    converted: list[dict[str, Json]] = []
    for m in messages:
        content = m.get("content", "")
        if not isinstance(content, list):
            converted.append(m)
            continue
        new_blocks: list[dict[str, Json]] = []
        for block in content:
            btype = block.get("type", "")
            if btype == "image_url":
                url = block.get("image_url", {}).get("url", "")
                if url.startswith("data:image/"):
                    # Extract base64 data
                    header, b64 = url.split(",", 1)
                    ext = _extract_image_ext(header)
                    try:
                        extracted = _upload_image_to_moonshot(
                            client=client, base64_data=b64, ext=ext
                        )
                        new_blocks.append({"type": "text", "text": f"[Image content extracted by AI]:\n{extracted}"})
                    except Exception as exc:
                        logger.warning("Failed to extract image via Moonshot file API: %s", exc)
                        new_blocks.append({"type": "text", "text": "[Image content could not be extracted]"})
                else:
                    # External URL — keep as text reference
                    new_blocks.append({"type": "text", "text": f"[Image URL]: {url}"})
            else:
                new_blocks.append(block)
        converted.append({**m, "content": new_blocks})
    return converted


def judge_chat_completion(
    messages: list[dict[str, Json]],
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> tuple[dict[str, Json] | None, dict[str, Json] | None, str]:
    """Drop-in replacement for raw OpenAI chat completions.

    Converts OpenAI-style message dicts to LangChain messages, invokes the judge,
    and returns an OpenAI-compatible response tuple.

    Args:
        messages: List of {"role": "system|user", "content": "..."} dicts.
        model, api_key, base_url: Passed to build_judge_llm().

    Returns:
        (full_response_dict, usage_dict, assistant_content_str)
        On error: (None, None, error_message_str)
    """
    model = model or os.environ.get("JUDGE_MODEL", "deepseek-v4-pro")
    api_key = api_key or os.environ.get("JUDGE_API_KEY")
    base_url = base_url or os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        raise ValueError("JUDGE_API_KEY not provided")

    # Moonshot image handling (only when using kimi models)
    if model.lower().startswith("kimi"):
        native_client = OpenAI(api_key=api_key, base_url=base_url)
        messages = _convert_messages_for_moonshot(messages=messages, client=native_client)

    llm = build_judge_llm(model=model, api_key=api_key, base_url=base_url)

    lc_messages = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        else:
            lc_messages.append(HumanMessage(content=content))

    try:
        response = llm.invoke(lc_messages)
        content = str(response.content) if response.content else ""

        # OpenAI-compatible response shape
        full_response = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ]
        }

        usage = {}
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage = {
                "prompt_tokens": um.get("input_tokens", 0),
                "completion_tokens": um.get("output_tokens", 0),
                "total_tokens": um.get("total_tokens", 0),
            }

        return full_response, usage, content

    except Exception as exc:
        err_msg = f"Judge LLM error: {type(exc).__name__}: {exc}"
        logger.error(err_msg)
        return None, None, err_msg


# ═══════════════════════════════════════════════════════════════
# 3. Convenience: pre-built singleton-like judge instance
# ═══════════════════════════════════════════════════════════════

_judge_instance: ChatOpenAI | None = None


def get_judge() -> ChatOpenAI:
    """Return a cached judge LLM instance (builds once, reuses afterwards).

    Usage:
        from workspace_bench_agent.judge_model import get_judge
        judge = get_judge()
        resp = judge.invoke([HumanMessage(content="Evaluate this output.")])
    """
    global _judge_instance
    if _judge_instance is None:
        _judge_instance = build_judge_llm()
    return _judge_instance


def reset_judge() -> None:
    """Clear the cached judge instance so next get_judge() rebuilds it."""
    global _judge_instance
    _judge_instance = None


# ═══════════════════════════════════════════════════════════════
# Smoke test
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("🔧 Judge LLM Smoke Test")
    print("=" * 40)

    try:
        judge = build_judge_llm()
        print(f"✅ Judge model created: {judge.model_name}")
        print(f"   base_url: {os.environ.get('JUDGE_BASE_URL', 'https://api.deepseek.com')}")
        print(f"   model:    {os.environ.get('JUDGE_MODEL', 'deepseek-v4-pro')}")

        # Quick invoke test
        resp = judge.invoke([HumanMessage(content="Say 'judge is ready' only.")])
        print(f"\n📨 Response: {resp.content}")
        print("\n✅ Judge instance is working!")

    except ValueError as exc:
        print(f"❌ {exc}")
        print("\n💡 To test, set the environment variable:")
        print("   export JUDGE_API_KEY='your-api-key'")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Invocation failed: {type(exc).__name__}: {exc}")
        sys.exit(1)
