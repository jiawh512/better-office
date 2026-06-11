"""Custom tools for workspace-bench tasks."""

# NOTE TO BETTER AGENT: When you add a new @tool function below, you MUST also:
#   1. Add its import to workspace_bench_agent/graph.py (e.g. "from workspace_bench_agent.tools import ..., new_tool")
#   2. Register it in the tools=[...] list inside build_agent() in graph.py.
# Otherwise the agent will not be able to use the new tool at runtime.

import os
from pathlib import Path

from langchain.tools import tool


def _resolve_path(path: str) -> Path:
    """Resolve a path relative to the task work directory."""
    work_dir = os.environ.get("WB_TASK_WORK_DIR", os.getcwd())
    p = Path(path)
    if p.is_absolute():
        return p
    return Path(work_dir) / p


@tool
def parse_pdf(path: str, max_pages: int = 20) -> str:
    """Extract text from a PDF file. Returns the text content.

    Use this instead of read_file for PDFs.

    Args:
        path: Path to the PDF file (relative to the task work directory).
        max_pages: Maximum pages to extract (default 20, to avoid token overflow).
    """
    try:
        import PyPDF2
    except ImportError:
        import subprocess

        subprocess.run(["pip", "install", "-q", "PyPDF2"], check=True)
        import PyPDF2

    p = _resolve_path(path)
    if not p.exists():
        return f"Error: File not found: {path}"

    try:
        reader = PyPDF2.PdfReader(str(p))
        total = len(reader.pages)
        pages_to_read = min(total, max_pages)
        texts = []
        for i in range(pages_to_read):
            page = reader.pages[i]
            texts.append(page.extract_text() or "")
        content = "\n".join(texts)
        if total > max_pages:
            content += f"\n\n[Truncated: {total - max_pages} more pages not shown]"
        return content
    except Exception as e:
        return f"Error parsing PDF: {e}"


@tool
def compute_hash(path: str, algorithm: str = "md5") -> str:
    """Compute a file hash using the specified algorithm.

    Use this for duplicate detection or file verification instead of
    reading large binary files with read_file.

    Args:
        path: Path to the file (relative to the task work directory).
        algorithm: Hash algorithm to use. One of "md5", "sha256", "sha1".
            Defaults to "md5".
    """
    import hashlib

    p = _resolve_path(path)
    if not p.exists():
        return f"Error: File not found: {path}"

    algo_map = {"md5": hashlib.md5, "sha256": hashlib.sha256, "sha1": hashlib.sha1}
    hasher_fn = algo_map.get(algorithm.lower())
    if hasher_fn is None:
        return f"Error: Unknown algorithm '{algorithm}'. Choose from: md5, sha256, sha1"

    try:
        h = hasher_fn()
        size = p.stat().st_size
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        digest = h.hexdigest()
        return f"{algorithm}:{digest}\nsize:{size}"
    except Exception as e:
        return f"Error computing hash: {e}"