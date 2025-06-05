import sys, types
from unittest.mock import MagicMock

redis_mod = types.ModuleType('redis')

class Pipeline:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        pass
    def set(self, *args, **kwargs):
        pass
    def lpush(self, *args, **kwargs):
        pass
    def hincrby(self, *args, **kwargs):
        pass
    def execute(self):
        pass

class RedisClient:
    def pipeline(self):
        return Pipeline()

def from_url(url):
    return RedisClient()

redis_mod.from_url = from_url
sys.modules['redis'] = redis_mod
