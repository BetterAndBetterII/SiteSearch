# 优化器
# 缩写；全称；译文；备注
import json
import os
import re
from openai.types.chat import ChatCompletionMessageParam

HINT_TEMPLATE = """
Hint for specific terms:
{hint}
"""

TERM_TEMPLATE = "- {term} stands for {full_name} and {translation} in Chinese.{remarks}"

class Optimizer:
    def __init__(self):

        # load_hint_table
        path = os.path.join(os.path.dirname(__file__), "hint_table.json")
        with open(path, "r", encoding="utf-8") as f:
            self.hint_table = json.load(f)

    def _get_hint(self, message: str) -> str:
        # 全词匹配
        exist_table = {k: False for k in self.hint_table.keys()}
        for key, value in self.hint_table.items():
            if key.lower() in message.lower():
                exist_table[key] = True

        if not any(exist_table.values()):
            print(">>>>>>>>>>>>>>>>>>>[hint]", "no hint")
            return ""

        # 如果存在，则返回
        hint_list = []
        for key, value in exist_table.items():
            if value:
                hint_list.append(
                    TERM_TEMPLATE.format(
                        term=key, 
                        full_name=self.hint_table[key]["full_name"], 
                        translation=self.hint_table[key]["translation"], 
                        remarks=f" ({self.hint_table[key]['remarks']})" if self.hint_table[key]["remarks"] else ""
                    )
                )
        hint = HINT_TEMPLATE.format(hint="\n".join(hint_list))
        print(">>>>>>>>>>>>>>>>>>>[hint]", hint)
        return hint

    def optimize(self, message: list[ChatCompletionMessageParam]) -> str:
        if len(message) == 0:
            return ""
        recent_message = message[-1]
        if 'content' not in recent_message:
            return ""
        content = "\n".join([c['text'] if 'text' in c else "" for c in recent_message['content']])
        hint = self._get_hint(content)
        return hint
