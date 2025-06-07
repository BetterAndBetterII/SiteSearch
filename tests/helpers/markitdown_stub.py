import sys, types

mod = types.ModuleType('markitdown')
class MarkItDown:
    def convert(self, path):
        class Result:
            text_content = ""
        return Result()

mod.MarkItDown = MarkItDown
sys.modules['markitdown'] = mod
