from datetime import datetime
from threading import Lock
from typing import Optional

from backend.sitesearch.crawler.base import CrawlerResult, CrawlerMetadata
from backend.sitesearch.crawler.base import DataCrawler
from crawlers.strategies import *
from file.sl_model import FileContent, get_db_session
from rag.models import get_db_session, init_db, Knowledge


class UploadCrawler(DataCrawler):
    """上传的文件数据采集器"""
    
    def __init__(self, timeout: int = 30, strategies: Optional[List[CleaningStrategy]] = None):
        super().__init__()
        init_db()
        self.lock = Lock()
        self.session = get_db_session()

        # 设置清洗策略，优先使用自定义策略
        self.strategies = strategies or [
            PDFStrategy(),
            DocxStrategy(),
            PlainTextStrategy(),  # 最后是纯文本清洗
        ]

    def clean_data(self, file: FileContent) -> str:
        """根据策略清洗数据

        Args:
            file: 上传的文件
            
        Returns:
            清洗后的内容
        """
        # 遍历所有策略，使用第一个匹配的策略
        if file.mimetype.startswith('text'):
            content_str = file.content.decode('utf-8')
        else:
            content_str = ""
        for strategy in self.strategies:
            if strategy.should_handle(url="", mimetype=file.mimetype, content=content_str):
                print(f"使用策略: {strategy.__class__.__name__}")
                return strategy.clean(content=file.content, content_str=content_str)

        # 如果没有匹配的策略，返回原始内容
        raise ValueError(f"没有匹配的策略: {file.mimetype}")
    
    def check_if_exists(self, file: FileContent) -> Optional[Knowledge]:
        """检查文件是否存在"""
        return self.session.query(Knowledge).filter(Knowledge.raw_content_hash == file.raw_content_hash).first()

    def crawl(self, file: FileContent) -> CrawlerResult:
        """爬取上传的文件"""

        if obj := self.check_if_exists(file):
            print(f"cache hit: {file.filename}")
            return CrawlerResult(
                mimetype=obj.mimetype,
                content=obj.content,
                metadata=CrawlerMetadata(**obj.result_metadata),
                raw_data=obj.raw_content_hash
            )

        # 清洗数据
        content = self.clean_data(file)

        file_metadata = file.result_metadata

        # 构建元数据
        metadata = CrawlerMetadata(
            source=file.source,
            url=file_metadata['url'],
            date=datetime.now(),
            title=file.filename,
        )

        crawler_result = CrawlerResult(
            mimetype=file.mimetype,
            content=content,
            metadata=metadata,
            raw_data=file.content
        )
        self.save_to_db(file, crawler_result)
        
        return crawler_result

    def save_to_db(self, file: FileContent, result: CrawlerResult):
        """将结果保存到数据库"""
        raw_content_hash = file.raw_content_hash
        with self.lock:
            knowledge = Knowledge(
                mimetype=result.mimetype,
                title=result.metadata.title,
                content=result.content,
                result_metadata=result.metadata.to_dict(),
                raw_content_hash=raw_content_hash,
                source=result.metadata.source,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_active=True
            )
            # 根据raw_content_hash查询已存在的知识条目
            existing_knowledges = self.session.query(Knowledge).filter(Knowledge.raw_content_hash == raw_content_hash)
            if existing_knowledges.count() > 1:
                print(f"raw_content_hash: {raw_content_hash} 存在 {existing_knowledges.count()} 条知识")
                latest_knowledge = existing_knowledges.order_by(Knowledge.updated_at.desc()).first()
                existing_knowledge = latest_knowledge
                # 删除其他重复的知识条目
                for knowledge in existing_knowledges:
                    if knowledge.id != latest_knowledge.id:
                        self.session.delete(knowledge)
            else:
                existing_knowledge = existing_knowledges.first()
            if existing_knowledge:
                existing_knowledge.mimetype = result.mimetype
                existing_knowledge.title = result.metadata.title
                existing_knowledge.content = result.content
                existing_knowledge.result_metadata = result.metadata.to_dict()
                existing_knowledge.updated_at = datetime.now()
                # 覆盖已存在的知识条目
                print(f"覆盖已存在的知识条目: {existing_knowledge.title}")
                self.session.merge(existing_knowledge)
            else:
                # 新增知识条目
                print(f"新增知识条目: {knowledge.title}")
                self.session.add(knowledge)

            self.session.commit()
        