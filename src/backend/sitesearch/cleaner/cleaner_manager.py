from typing import List
from .cleaner_strategy import (
    CleaningStrategy,
    PDFStrategy,
    DocxStrategy,
    SearchPageStrategy,
    CommonPageStrategy,
    MarkdownStrategy,
    HTMLStrategy,
    PlainTextStrategy,
    MarkItDownStrategy
)

class DataCleaner:
    def __init__(self, strategies: List[CleaningStrategy] = None):
        self.strategies = strategies or [
            PDFStrategy(),
            DocxStrategy(),
            MarkItDownStrategy(),
            SearchPageStrategy(),  # 针对搜索页面的策略
            CommonPageStrategy(),  # 优先使用针对常见page页面的策略
            MarkdownStrategy(),  # 其次尝试转换为Markdown
            HTMLStrategy(),  # 再次尝试普通HTML清洗
            PlainTextStrategy(),  # 最后是纯文本清洗
        ]

    def add_strategy(self, strategy):
        self.strategies.append(strategy)

    def clean(self, url: str, mimetype: str, content: bytes | str) -> str:
        for strategy in self.strategies:
            if strategy.should_handle(url, mimetype, content):
                return strategy.clean(content)
        return content
