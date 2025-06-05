import pytest
from src.backend.tools.markdown_tools import parse_links, replace_base64, clean_md


def test_parse_links():
    text = "This [link](http://example.com) and ![img](image.png)"
    assert parse_links(text) == ["http://example.com", "image.png"]


def test_replace_base64():
    content = "![pic](data:image/png;base64,xxxx)"
    assert replace_base64(content) == "![pic](base64_image)"


def test_clean_md():
    raw = " line1  \n\n![i](data:image/jpeg;base64,abc)\n  line2   "
    assert clean_md(raw) == "line1\n\nline2"
