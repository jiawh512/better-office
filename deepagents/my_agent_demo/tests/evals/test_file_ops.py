"""Eval cases for file operation tools."""
import os
import tempfile

import pytest

from my_agent.graph import build_agent


@pytest.fixture
def agent():
    return build_agent()


class TestFileOperations:
    """Test that the agent correctly uses file read/write tools."""

    def test_write_and_read_file(self, agent):
        """train: Agent should write a file and confirm."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            result = agent.invoke(
                {"messages": f'Write "Hello World" to {filepath}'}
            )
            output = str(result["messages"][-1].content)
            assert os.path.exists(filepath), "File should be created"
            with open(filepath) as f:
                content = f.read()
            assert "Hello World" in content, f"Expected 'Hello World' in file, got: {content}"

    def test_read_existing_file(self, agent):
        """holdout: Agent should read an existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "data.txt")
            with open(filepath, "w") as f:
                f.write("Sample data: 42")

            result = agent.invoke(
                {"messages": f'Read the content of {filepath}'}
            )
            output = str(result["messages"][-1].content)
            assert "42" in output, f"Expected 42 in output, got: {output}"
