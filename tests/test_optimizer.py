import json
from pathlib import Path
import importlib.util

from tests.helpers import openai_stub  # noqa: F401

# Load Optimizer without importing package __init__
module_path = Path(__file__).resolve().parents[1] / 'src/backend/sitesearch/agent/optimizer.py'
spec = importlib.util.spec_from_file_location('optimizer', module_path)
optimizer_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimizer_mod)
Optimizer = optimizer_mod.Optimizer


def create_hint_file(tmp_path: Path):
    data = {
        "AI": {
            "full_name": "Artificial Intelligence",
            "translation": "\u4eba\u5de5\u667a\u80fd",
            "remarks": ""
        },
        "NLP": {
            "full_name": "Natural Language Processing",
            "translation": "\u81ea\u7136\u8bed\u8a00\u5904\u7406",
            "remarks": "remark"
        }
    }
    file_path = tmp_path / "hint_table.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return file_path


def test_get_hint(tmp_path):
    hint_file = create_hint_file(tmp_path)
    opt = Optimizer(hint_table_path=str(hint_file))
    hint = opt._get_hint("This talks about AI and nothing else")
    expected = (
        "Hint for specific terms:\n"
        "- AI stands for Artificial Intelligence and \u4eba\u5de5\u667a\u80fd in Chinese."
    )
    assert hint.strip() == expected


def test_get_hint_none(tmp_path):
    hint_file = create_hint_file(tmp_path)
    opt = Optimizer(hint_table_path=str(hint_file))
    assert opt._get_hint("Nothing here") == ""


def test_optimize(tmp_path):
    hint_file = create_hint_file(tmp_path)
    opt = Optimizer(hint_table_path=str(hint_file))
    message = [{"role": "user", "content": "Tell me about AI"}]
    assert "Artificial Intelligence" in opt.optimize(message)
