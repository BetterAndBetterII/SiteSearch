import sys, types

asgiref_mod = types.ModuleType('asgiref')
sync_mod = types.ModuleType('asgiref.sync')

async def sync_to_async(fn):
    async def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

sync_mod.sync_to_async = sync_to_async

sys.modules['asgiref'] = asgiref_mod
sys.modules['asgiref.sync'] = sync_mod
