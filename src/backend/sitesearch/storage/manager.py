from src.backend.sitesearch.storage.models import Document, CrawlHistory
from src.backend.sitesearch.storage.utils import store_document, get_document_by_url, get_document_by_hash, get_documents_by_site, get_pending_index_documents, mark_document_indexed, delete_document, get_document_history, search_documents, get_storage_stats, check_document_exists
import logging
from typing import Dict, Tuple, Optional, List, Any

class DataStorage:
    """数据存储器，处理所有数据存储相关的操作"""
    
    def __init__(self):
        """初始化数据存储器"""
        self.logger = logging.getLogger('storage.DataStorage')
    
    def save_document(self, data: Dict[str, Any]) -> Tuple[Document, str]:
        """
        保存文档数据，处理新增、更新和跳过的情况
        
        Args:
            data: 包含文档所有字段的字典数据
            
        Returns:
            Tuple[Document, str]: 返回(文档对象, 操作类型)
            操作类型可能是: 'new', 'edit', 'skip', 'error'
        """
        try:
            # 调用工具函数存储文档
            return store_document(data)
        except Exception as e:
            self.logger.error(f"保存文档时发生错误: {str(e)}")
            raise
    
    def get_document(self, url: str = None, content_hash: str = None) -> Optional[Document]:
        """
        获取文档，支持通过URL或内容哈希获取
        
        Args:
            url: 文档URL
            content_hash: 文档内容哈希值
            
        Returns:
            Optional[Document]: 文档对象，如果不存在则返回None
        """
        if url:
            return get_document_by_url(url)
        elif content_hash:
            return get_document_by_hash(content_hash)
        return None
    
    def get_site_documents(self, site_id: str, limit: int = 100, offset: int = 0) -> List[Document]:
        """
        获取指定站点的所有文档
        
        Args:
            site_id: 站点ID
            limit: 返回结果数量限制
            offset: 结果偏移量
            
        Returns:
            List[Document]: 文档列表
        """
        return get_documents_by_site(site_id, limit, offset)
    
    def get_pending_documents(self, limit: int = 50) -> List[Document]:
        """
        获取待索引的文档列表
        
        Args:
            limit: 返回结果数量限制
            
        Returns:
            List[Document]: 待索引的文档列表
        """
        return get_pending_index_documents(limit)
    
    def mark_indexed(self, document_id: int, indexed: bool = True) -> bool:
        """
        标记文档的索引状态
        
        Args:
            document_id: 文档ID
            indexed: 是否已索引
            
        Returns:
            bool: 操作是否成功
        """
        return mark_document_indexed(document_id, indexed)
    
    def delete_document(self, url: str) -> bool:
        """
        删除文档
        
        Args:
            url: 文档URL
            
        Returns:
            bool: 是否成功删除
        """
        return delete_document(url)
    
    def get_document_history(self, url: str) -> List[CrawlHistory]:
        """
        获取文档的历史记录
        
        Args:
            url: 文档URL
            
        Returns:
            List[CrawlHistory]: 历史记录列表
        """
        return get_document_history(url)
    
    def search_documents(self, query: str, site_id: Optional[str] = None, limit: int = 50) -> List[Document]:
        """
        搜索文档（基于数据库的简单搜索）
        
        Args:
            query: 搜索查询
            site_id: 限制在特定站点内搜索
            limit: 结果数量限制
            
        Returns:
            List[Document]: 匹配的文档列表
        """
        return search_documents(query, site_id, limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取存储统计信息
        
        Returns:
            Dict[str, Any]: 存储统计信息字典
        """
        return get_storage_stats()
    
    def check_exists(self, url: str, content_hash: Optional[str] = None) -> Tuple[bool, Optional[Document], str]:
        """
        检查文档是否存在
        
        Args:
            url: 文档URL
            content_hash: 内容哈希值（可选）
            
        Returns:
            Tuple[bool, Optional[Document], str]: 
                - 是否存在
                - 存在的文档对象（如果有）
                - 操作类型（'new'/'edit'/'skip'）
        """
        return check_document_exists(url, content_hash)
    