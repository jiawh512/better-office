"""Eval cases for calculator tool usage."""
import pytest

from my_agent.graph import build_agent


@pytest.fixture
def agent():
    return build_agent()


class TestCalculator:
    """Test that the agent correctly uses the calculator tool."""

    def test_basic_addition(self, agent):
        """train: Agent should calculate 15 + 27."""
        result = agent.invoke({"messages": "What is 15 + 27?"})
        output = str(result["messages"][-1].content)
        assert "42" in output, f"Expected 42 in output, got: {output}"

    def test_complex_expression(self, agent):
        """train: Agent should calculate (100 - 30) * 2."""
        result = agent.invoke({"messages": "Calculate (100 - 30) multiplied by 2"})
        output = str(result["messages"][-1].content)
        assert "140" in output, f"Expected 140 in output, got: {output}"

    def test_division(self, agent):
        """holdout: Agent should calculate 81 / 9."""
        result = agent.invoke({"messages": "What is 81 divided by 9?"})
        output = str(result["messages"][-1].content)
        assert "9" in output, f"Expected 9 in output, got: {output}"

    def test_multiplication(self, agent):
        """holdout: Agent should calculate 12 * 12."""
        result = agent.invoke({"messages": "What is 12 times 12?"})
        output = str(result["messages"][-1].content)
        assert "144" in output, f"Expected 144 in output, got: {output}"
