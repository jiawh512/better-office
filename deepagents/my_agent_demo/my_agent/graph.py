"""Agent graph setup for the demo agent."""
import logging
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from my_agent.tools import calculator, get_weather, read_file, write_file

# ========== 日志配置：同时输出到控制台 + 文件 ==========
os.makedirs("logs", exist_ok=True)

_log_filename = f"logs/agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),  # 控制台
        logging.FileHandler(_log_filename, encoding="utf-8"),  # 本地文件
    ],
    force=True,  # 强制覆盖之前的 logging 配置
)
logger = logging.getLogger(__name__)


BASE_PROMPT = """\
You are a potato.
"""


def _safe_repr(obj, max_len=500):
    """安全序列化对象"""
    text = str(obj)
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def _wrap_tool(tool):
    """给 tool 加日志包装，记录每次调用入参和出参"""
    original_invoke = tool.invoke

    def logged_invoke(*args, **kwargs):
        tool_input = kwargs.get("input", args[0] if args else {})
        logger.info(f"🔧 调用工具 [{tool.name}] | 参数: {_safe_repr(tool_input)}")
        result = original_invoke(*args, **kwargs)
        logger.info(f"✅ 工具 [{tool.name}] 返回 | {_safe_repr(result)}")
        return result

    # 绕过 Pydantic v2 的 __setattr__ 检查 
    object.__setattr__(tool, 'invoke', logged_invoke)
    return tool


def _wrap_llm(llm):
    """Wraps the LLM's invoke to log inputs/outputs."""
    original_invoke = llm.invoke

    def logged_invoke(*args, **kwargs):
        # 这里放你的日志逻辑
        # 例如：print(f"[LLM Invoke] {args}, {kwargs}")
        result = original_invoke(*args, **kwargs)
        # 例如：print(f"[LLM Result] {result}")
        return result

    # 关键：绕过 Pydantic v2 的 __setattr__ 检查
    object.__setattr__(llm, 'invoke', logged_invoke)
    return llm


def build_agent(model: str = "deepseek-v4-flash"):
    """Build and return the agent."""
    llm = ChatOpenAI(
        model=model,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_API_BASE", "https://api.deepseek.com"),
        extra_body={"thinking": {"type": "disabled"}},
    )

    # 包装 LLM 和 Tools，确保每次调用都有日志
    logged_llm = _wrap_llm(llm)
    # BASELINE: intentionally omit custom tools so the harness must restore them
    logged_tools = []

    return create_deep_agent(
        model=logged_llm,
        tools=logged_tools,
        middleware=[],  # middleware 钩子不工作，清空避免干扰
        system_prompt=BASE_PROMPT,
    )
