import asyncio
import json

from src.backend.tools.json_tools import format_as_ndjson, JSONEncoder_with_dataclasses

async def async_gen(n):
    for i in range(n):
        yield {"num": i}


def test_format_as_ndjson_basic():
    async def collect():
        lines = []
        async for line in format_as_ndjson(async_gen(2)):
            lines.append(line)
        return lines
    lines = asyncio.run(collect())
    assert lines == [
        json.dumps({"num": 0}, ensure_ascii=False, cls=JSONEncoder_with_dataclasses) + "\n",
        json.dumps({"num": 1}, ensure_ascii=False, cls=JSONEncoder_with_dataclasses) + "\n",
    ]


async def error_gen():
    yield {"a": 1}
    raise ValueError("oops")


def test_format_as_ndjson_error():
    async def collect():
        lines = []
        async for line in format_as_ndjson(error_gen()):
            lines.append(line)
        return lines
    lines = asyncio.run(collect())
    assert lines[-1] == json.dumps({"error": "oops"})
