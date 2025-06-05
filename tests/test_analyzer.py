import types
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, patch
import asyncio

from tests.helpers import openai_stub  # noqa: F401

module_path = Path(__file__).resolve().parents[1] / 'src/backend/sitesearch/agent/analyzer.py'
spec = importlib.util.spec_from_file_location('analyzer', module_path)
analyzer_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer_mod)
Analyzer = analyzer_mod.Analyzer
AnalyzerPrompt = analyzer_mod.AnalyzerPrompt


class DummyClient:
    def __init__(self, content: str):
        class _Completions:
            async def create(self_inner, *args, **kwargs):
                return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))])
        self.chat = types.SimpleNamespace(completions=_Completions())


def test_analyze_basic():
    client = DummyClient("one\ntwo\nthree")
    analyzer = Analyzer(client, model='dummy')
    result = asyncio.run(analyzer.analyze("hi", AnalyzerPrompt.CONTEXT_PROMPT, item_count=2))
    assert result == ["one", "two", "three"]


def test_analyze_kmds():
    client = DummyClient("unused")
    analyzer = Analyzer(client)
    with patch.object(Analyzer, 'analyze', new=AsyncMock(side_effect=[["k"], ["m"], ["d"], ["s"]])):
        results = asyncio.run(analyzer.analyze_kmds("q", item_count=1))
    assert results == [["k"], ["m"], ["d"], ["s"]]
