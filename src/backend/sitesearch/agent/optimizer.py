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
    def __init__(self, hint_table_path=None):
        # 默认的hint_table.json路径
        if hint_table_path is None:
            hint_table_path = os.path.join(os.path.dirname(__file__), "data", "hint_table.json")
        
        try:
            with open(hint_table_path, "r", encoding="utf-8") as f:
                self.hint_table = json.load(f)
            print(f"成功加载提示词表: {hint_table_path}")
        except FileNotFoundError:
            print(f"提示词表文件未找到: {hint_table_path}，使用空表")
            self.hint_table = {}
        except json.JSONDecodeError:
            print(f"提示词表格式错误: {hint_table_path}，使用空表")
            self.hint_table = {}

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
        
        # 如果content是字符串，直接使用，否则尝试获取文本部分
        if isinstance(recent_message['content'], str):
            content = recent_message['content']
        else:
            content = "\n".join([c.get('text', '') for c in recent_message['content'] if isinstance(c, dict)])
        
        hint = self._get_hint(content)
        return hint 