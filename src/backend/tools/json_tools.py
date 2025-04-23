import json
from typing import Generator
import dataclasses
import traceback

class JSONEncoder_with_dataclasses(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return super().default(o)

async def format_as_ndjson(r):
    """Format the response stream as ndjson.
    Args:
        r (AsyncGenerator[dict, None]): A generator that yields dictionaries.
    Returns:
        A generator that yields ndjson strings.
    """
    try:
        async for event in r:
            # print(event)
            yield json.dumps(event, ensure_ascii=False, cls=JSONEncoder_with_dataclasses) + "\n"
    except Exception as error:
        traceback.print_exc()
        yield json.dumps({
            "error": str(error)
        })
