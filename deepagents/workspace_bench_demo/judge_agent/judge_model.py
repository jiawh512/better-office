"""Judge LLM instance — LangChain ChatOpenAI for the evaluator.

Provides robust connection config (timeout, retries) for the judge,
similar to the inner agent's ChatOpenAI setup.
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


def build_judge_llm(
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.0,
) -> ChatOpenAI:
    """Build and return a ChatOpenAI instance for judge (evaluator)."""
    model = model or os.environ.get("JUDGE_MODEL", "deepseek-v4-pro")
    api_key = api_key or os.environ.get("JUDGE_API_KEY")
    base_url = base_url or os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        raise ValueError("JUDGE_API_KEY not provided")

    logger.info("Building judge LLM: model=%s, base_url=%s", model, base_url)

    _http_client = httpx.Client(http2=False)

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(
            connect=5.0,
            read=60.0,
            write=10.0,
            pool=5.0,
        ),
        max_retries=5,
        streaming=False,
        temperature=temperature,
        extra_body={"thinking": {"type": "disabled"}},
        http_client=_http_client,
    )


def _extract_image_ext(url: str) -> str:
    if url.startswith("data:image/"):
        mime = url.split(";")[0].split("/")[1]
        return mime if mime else "png"
    return "png"


def _upload_image_to_moonshot(*, client: OpenAI, base64_data: str, ext: str) -> str:
    image_bytes = base64.b64decode(base64_data)
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
    *, messages: list[dict[str, Json]], client: OpenAI
) -> list[dict[str, Json]]:
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
                    header, b64 = url.split(",", 1)
                    ext = _extract_image_ext(header)
                    try:
                        extracted = _upload_image_to_moonshot(
                            client=client, base64_data=b64, ext=ext
                        )
                        new_blocks.append(
                            {
                                "type": "text",
                                "text": f"[Image content extracted by AI]:\n{extracted}",
                            }
                        )
                    except Exception as exc:
                        logger.warning("Failed to extract image via Moonshot: %s", exc)
                        new_blocks.append(
                            {"type": "text", "text": "[Image content could not be extracted]"}
                        )
                else:
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

    Returns:
        (full_response_dict, usage_dict, assistant_content_str)
        On error: (None, None, error_message_str)
    """
    model = model or os.environ.get("JUDGE_MODEL", "deepseek-v4-pro")
    api_key = api_key or os.environ.get("JUDGE_API_KEY")
    base_url = base_url or os.environ.get("JUDGE_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        raise ValueError("JUDGE_API_KEY not provided")

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


_judge_instance: ChatOpenAI | None = None


def get_judge() -> ChatOpenAI:
    """Return a cached judge LLM instance."""
    global _judge_instance
    if _judge_instance is None:
        _judge_instance = build_judge_llm()
    return _judge_instance


def reset_judge() -> None:
    """Clear the cached judge instance."""
    global _judge_instance
    _judge_instance = None
