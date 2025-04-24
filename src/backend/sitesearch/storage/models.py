"""
存储模块的数据模型定义
定义与PostgreSQL数据库交互的ORM模型
"""

from django.db import models
from datetime import datetime


class Document(models.Model):
    """
    文档模型，存储爬取的网页内容和元数据
    """
    # 基础信息
    url = models.URLField(max_length=2048, unique=True, db_index=True, help_text="页面URL")
    content = models.TextField(help_text="页面原始内容")
    clean_content = models.TextField(null=True, blank=True, help_text="清洗后的Markdown内容")
    status_code = models.IntegerField(default=200, help_text="HTTP状态码")
    headers = models.JSONField(default=dict, help_text="HTTP响应头")
    timestamp = models.BigIntegerField(help_text="爬取时间戳")
    links = models.JSONField(default=list, help_text="页面中提取的链接列表")
    mimetype = models.CharField(max_length=255, help_text="内容MIME类型")
    
    # 元数据
    title = models.CharField(max_length=1024, null=True, blank=True, help_text="页面标题")
    description = models.TextField(null=True, blank=True, help_text="页面描述")
    keywords = models.TextField(null=True, blank=True, help_text="关键词")
    source = models.CharField(max_length=255, help_text="域名来源")
    metadata = models.JSONField(default=dict, help_text="其他元数据")
    
    # 爬虫相关
    content_hash = models.CharField(max_length=64, db_index=True, help_text="内容哈希值，用于去重和变更检测")
    crawler_id = models.CharField(max_length=255, help_text="爬虫ID")
    crawler_type = models.CharField(max_length=50, help_text="爬虫类型")
    crawler_config = models.JSONField(default=dict, help_text="爬虫配置")
    
    # 版本控制
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    updated_at = models.DateTimeField(auto_now=True, help_text="更新时间")
    version = models.IntegerField(default=1, help_text="版本号")
    index_operation = models.CharField(max_length=10, default="new", 
                                       choices=[("new", "新增"), ("edit", "更新"), ("delete", "删除")],
                                       help_text="索引操作类型")
    is_indexed = models.BooleanField(default=False, help_text="是否已索引")
    
    class Meta:
        db_table = 'sitesearch_document'
        indexes = [
            models.Index(fields=['content_hash']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_indexed']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.url} ({self.content_hash[:8]})"
    
    def set_metadata(self, metadata_dict):
        """
        设置元数据，从字典提取关键字段到模型属性
        """
        # 保存完整元数据到JSON字段
        self.metadata = metadata_dict
        
        # 提取关键字段到独立列
        if metadata_dict:
            self.title = metadata_dict.get('title')
            self.description = metadata_dict.get('description')
            self.keywords = metadata_dict.get('keywords')
            
            # 从元数据中提取更多内容
            if 'og_title' in metadata_dict and not self.title:
                self.title = metadata_dict.get('og_title')
            
            if 'og_description' in metadata_dict and not self.description:
                self.description = metadata_dict.get('meta_description')
    
    @classmethod
    def from_crawler_data(cls, data):
        """
        从爬虫数据创建文档实例
        """
        document = cls(
            url=data['url'],
            content=data['content'],
            clean_content=data.get('clean_content'),
            status_code=data.get('status_code', 200),
            headers=data.get('headers', {}),
            timestamp=data.get('timestamp', int(datetime.now().timestamp())),
            links=data.get('links', []),
            mimetype=data.get('mimetype', 'text/html'),
            source=data.get('metadata', {}).get('source', ''),
            content_hash=data.get('content_hash', ''),
            crawler_id=data.get('crawler_id', ''),
            crawler_type=data.get('crawler_type', ''),
            crawler_config=data.get('crawler_config', {}),
            index_operation=data.get('index_operation', 'new')
        )
        
        # 设置元数据
        document.set_metadata(data.get('metadata', {}))
        
        return document
    
    def get_site_ids(self):
        """
        获取文档关联的所有站点ID
        
        Returns:
            List[str]: 站点ID列表
        """
        return list(self.sites.values_list('site_id', flat=True))
    
    def add_to_site(self, site_id):
        """
        将文档添加到指定站点
        
        Args:
            site_id: 站点ID
            
        Returns:
            SiteDocument: 创建的站点文档关联对象
        """
        site_doc, created = SiteDocument.objects.get_or_create(
            document=self,
            site_id=site_id
        )
        return site_doc
    
    def remove_from_site(self, site_id):
        """
        从指定站点移除文档
        
        Args:
            site_id: 站点ID
            
        Returns:
            bool: 是否成功移除
        """
        count, _ = SiteDocument.objects.filter(document=self, site_id=site_id).delete()
        return count > 0
    
    @property
    def primary_site_id(self):
        """
        获取文档的主站点ID（第一个添加的站点）
        用于向后兼容
        
        Returns:
            str: 主站点ID，如果没有则返回空字符串
        """
        site = self.sites.order_by('created_at').first()
        return site.site_id if site else ""


class SiteDocument(models.Model):
    """
    站点-文档关联模型，实现文档可以归属于多个站点
    """
    site_id = models.CharField(max_length=255, db_index=True, help_text="站点ID")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='sites')
    created_at = models.DateTimeField(auto_now_add=True, help_text="创建时间")
    
    class Meta:
        db_table = 'sitesearch_site_document'
        unique_together = ('site_id', 'document')
        indexes = [
            models.Index(fields=['site_id']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.site_id} - {self.document.url}"


class CrawlHistory(models.Model):
    """
    爬取历史记录，用于版本控制和变更追踪
    """
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='history')
    content_hash = models.CharField(max_length=64, db_index=True, help_text="内容哈希值")
    url = models.URLField(max_length=2048, db_index=True, help_text="页面URL")
    timestamp = models.BigIntegerField(help_text="爬取时间戳")
    version = models.IntegerField(help_text="版本号")
    change_type = models.CharField(max_length=10, 
                                  choices=[("new", "新增"), ("edit", "更新"), ("delete", "删除")],
                                  help_text="变更类型")
    created_at = models.DateTimeField(auto_now_add=True, help_text="记录创建时间")
    metadata = models.JSONField(default=dict, help_text="变更元数据")
    
    class Meta:
        db_table = 'sitesearch_crawl_history'
        indexes = [
            models.Index(fields=['content_hash']),
            models.Index(fields=['url']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.url} (v{self.version}, {self.change_type})"
    
    @classmethod
    def from_document(cls, document, change_type="new"):
        """
        从文档创建历史记录
        """
        history = cls(
            document=document,
            content_hash=document.content_hash,
            url=document.url,
            timestamp=document.timestamp,
            version=document.version,
            change_type=change_type,
            metadata={
                "title": document.title,
                "description": document.description,
                "content_length": len(document.content) if document.content else 0,
                "clean_content_length": len(document.clean_content) if document.clean_content else 0,
                "crawler_id": document.crawler_id,
                "site_ids": document.get_site_ids()
            }
        )
        return history 
