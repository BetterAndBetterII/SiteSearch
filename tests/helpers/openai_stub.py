import sys, types

openai_mod = types.ModuleType('openai')
openai_types = types.ModuleType('openai.types')
chat_mod = types.ModuleType('openai.types.chat')

class AsyncOpenAI:
    def __init__(self, *args, **kwargs):
        pass

setattr(chat_mod, 'ChatCompletionMessageParam', dict)
openai_mod.AsyncOpenAI = AsyncOpenAI
openai_mod.types = types.SimpleNamespace(chat=chat_mod)

sys.modules['openai'] = openai_mod
sys.modules['openai.types'] = openai_types
sys.modules['openai.types.chat'] = chat_mod
