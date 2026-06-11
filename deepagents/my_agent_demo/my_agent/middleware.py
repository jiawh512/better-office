"""Custom middleware for the demo agent."""
import logging
import os
from datetime import datetime

from langchain.agents.middleware import AgentMiddleware

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"logs/agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def _safe_repr(obj, max_len=500):
    """安全序列化：支持 HumanMessage / AIMessage / ToolCallRequest 等对象"""
    try:
        if hasattr(obj, "model_dump"):
            text = str(obj.model_dump())
        elif hasattr(obj, "to_dict"):
            text = str(obj.to_dict())
        else:
            text = str(obj)
    except Exception:
        text = repr(obj)
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


class LogMiddleware(AgentMiddleware):
    """Logs all agent inputs and outputs."""

    def before_agent(self, inputs, **kwargs):
        logger.info(f"🟢 Agent 启动 | 输入: {_safe_repr(inputs)}")

    def after_agent(self, outputs, **kwargs):
        logger.info(f"🔴 Agent 结束 | 输出: {_safe_repr(outputs)}")

    def before_model(self, messages, **kwargs):
        logger.info(f"🧠 LLM 调用前 | 消息: {_safe_repr(messages, max_len=800)}")

    def after_model(self, response, **kwargs):
        logger.info(f"📝 LLM 返回后 | {_safe_repr(response, max_len=800)}")

    def wrap_tool_call(self, request, handler):
        """包装工具调用：request = ToolCallRequest, handler = 实际执行函数"""
        # 从 ToolCallRequest 里提取工具名和参数
        tool_call_data = getattr(request, "tool_call", request)
        if isinstance(tool_call_data, dict):
            tool_name = tool_call_data.get("name", str(request))
            tool_args = tool_call_data.get("args", {})
        else:
            tool_name = getattr(request, "name", str(request))
            tool_args = getattr(request, "args", {})
        
        logger.info(f"🔧 调用工具 | {tool_name} | 参数: {_safe_repr(tool_args)}")
        result = handler(request)
        logger.info(f"✅ 工具返回 | {tool_name} | 结果: {_safe_repr(result)}")
        return result

    def wrap_model_call(self, request, handler):
        """包装模型调用"""
        logger.info(f"🧠 模型调用 | 请求: {_safe_repr(request, max_len=600)}")
        result = handler(request)
        logger.info(f"📝 模型返回 | {_safe_repr(result, max_len=600)}")
        return result

    # async 版本
    async def abefore_agent(self, inputs, **kwargs):
        self.before_agent(inputs, **kwargs)

    async def aafter_agent(self, outputs, **kwargs):
        self.after_agent(outputs, **kwargs)

    async def abefore_model(self, messages, **kwargs):
        self.before_model(messages, **kwargs)

    async def aafter_model(self, response, **kwargs):
        self.after_model(response, **kwargs)

    async def awrap_tool_call(self, request, handler):
        return self.wrap_tool_call(request, handler)

    async def awrap_model_call(self, request, handler):
        return self.wrap_model_call(request, handler)
