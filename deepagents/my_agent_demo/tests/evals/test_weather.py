"""Eval cases for weather tool usage."""
import pytest

from my_agent.graph import build_agent


@pytest.fixture
def agent():
    return build_agent()


class TestWeather:
    """Test that the agent correctly uses the weather tool."""

    def test_weather_query(self, agent):
        """train: Agent should check weather for Beijing."""
        result = agent.invoke({"messages": "What's the weather like in Beijing?"})
        output = str(result["messages"][-1].content)
        assert "Beijing" in output, f"Expected Beijing in output, got: {output}"
        assert "sunny" in output.lower() or "25" in output, f"Expected weather info, got: {output}"

    def test_weather_shanghai(self, agent):
        """holdout: Agent should check weather for Shanghai."""
        result = agent.invoke({"messages": "Tell me the weather in Shanghai"})
        output = str(result["messages"][-1].content)
        assert "Shanghai" in output, f"Expected Shanghai in output, got: {output}"
