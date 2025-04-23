import hashlib
from datetime import datetime
from threading import Lock
from typing import Optional
import mimetypes
import tempfile

from backend.sitesearch.crawler.base import CrawlerResult, CrawlerMetadata
from backend.sitesearch.crawler.base import DataCrawler
from crawlers.strategies import *
from rag.models import get_db_session, init_db, Knowledge


class EmailCrawler(DataCrawler):
    """邮件数据采集器"""

    def __init__(self, strategies: Optional[List[CleaningStrategy]] = None):
        super().__init__()
        init_db()
        self.lock = Lock()
        self.session = get_db_session()

        # 设置清洗策略，优先使用自定义策略
        self.strategies = strategies or [
            PDFStrategy(),
            DocxStrategy(),
            ImageDiscardStrategy(),
            PlainTextStrategy(),  # 最后是纯文本清洗
        ]

    def clean_data(self, url: str, mimetype: str, content: bytes, content_str: str) -> str:
        """根据策略清洗数据

        Args:
            url: 邮件的URL
            mimetype: 邮件的MIME类型
            content: 邮件的二进制内容
            content_str: 邮件的文本内容

        Returns:
            清洗后的内容
        """
        # 遍历所有策略，使用第一个匹配的策略
        if mimetype.startswith('text'):
            content_str = content_str
        else:
            content_str = ""

        for strategy in self.strategies:
            if strategy.should_handle(url="", mimetype=mimetype, content=content_str):
                print(f"使用策略: {strategy.__class__.__name__}")
                return strategy.clean(content=content, content_str=content_str)

        # 如果没有匹配的策略，返回原始内容
        raise ValueError(f"没有匹配的策略: {mimetype}")


    def check_if_exists(self, content_str: str | bytes) -> Optional[Knowledge]:
        """检查邮件是否存在"""
        if isinstance(content_str, bytes):
            raw_content_hash = hashlib.sha256(content_str).hexdigest()
        else:
            raw_content_hash = hashlib.sha256(content_str.encode()).hexdigest()
        return self.session.query(Knowledge).filter(Knowledge.raw_content_hash == raw_content_hash).first()


    def crawl(self, message):
        """爬取邮件"""
        full_email_content = message.Body
        mimetype = "text/plain"

        if not self.check_if_exists(full_email_content):
            content = self.clean_data(message.SenderEmailAddress, mimetype, full_email_content, full_email_content)
            metadata = CrawlerMetadata(
                source=message.SenderEmailAddress,
                url=message.SenderEmailAddress,
                date=datetime.now(),
                title=message.Subject,
            )
            
            crawler_result = CrawlerResult(
                mimetype=mimetype,
                content=content,
                metadata=metadata,
                raw_data=full_email_content
            )
            self.save_to_db(crawler_result)
        else:
            print(f"cache hit: {message.Subject}")

        attachments = message.Attachments
        if message.Attachments.Count > 0:
            print(f"邮件 {message.Subject} 有 {message.Attachments.Count} 个附件")
        for attachment in attachments:
            attachment_filename = attachment.FileName
            # 根据文件扩展名判断MIME类型
            attachment_mimetype = mimetypes.guess_type(attachment_filename)[0] or 'application/octet-stream'
            tempfile_path = tempfile.mktemp()
            attachment.SaveAsFile(tempfile_path)
            with open(tempfile_path, "rb") as f:
                attachment_content = f.read()

            if self.check_if_exists(attachment_content):
                print(f"cache hit: {attachment_filename}")
                continue

            # 清洗数据
            attachment_content_str = attachment_content.decode("utf-8", errors="ignore")
            try:
                content = self.clean_data(message.SenderEmailAddress, attachment_mimetype, attachment_content, attachment_content_str)
                if not content:
                    continue
            except Exception as e:
                print(f"清洗数据失败: {e}")
                continue

            # 构建元数据
            metadata = CrawlerMetadata(
                source=message.SenderEmailAddress,
                url=message.SenderEmailAddress,
                date=message.SentOn,
                title=f"{message.Subject} - {attachment_filename}",
            )

            crawler_result = CrawlerResult(
                mimetype=attachment_mimetype,
                content=content,
                metadata=metadata,
                raw_data=attachment_content_str
            )

            self.save_to_db(crawler_result)


    def save_to_db(self, result: CrawlerResult):
        """将结果保存到数据库"""
        raw_content_hash = hashlib.sha256(result.raw_data.encode()).hexdigest()
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
