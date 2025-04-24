from src.backend.sitesearch.storage.models import Document, CrawlHistory, SiteDocument
from src.backend.sitesearch.storage.utils import store_document, get_document_by_url, get_document_by_hash, get_documents_by_site, get_pending_index_documents, mark_document_indexed, delete_document, get_document_history, search_documents, get_storage_stats, check_document_exists, add_document_to_site, remove_document_from_site, get_document_sites, check_document_in_site
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
            操作类型可能是: 'new', 'edit', 'skip', 'new_site', 'error'
        """
        try:
            # 调用工具函数存储文档
            return store_document(data)
        except Exception as e:
            self.logger.error(f"保存文档时发生错误: {str(e)}")
            raise
    
    def get_document(self, url: str = None, content_hash: str = None, site_id: str = None) -> Optional[Document]:
        """
        获取文档，支持通过URL或内容哈希获取
        
        Args:
            url: 文档URL
            content_hash: 文档内容哈希值
            site_id: 站点ID，如果提供则验证文档是否在该站点中
            
        Returns:
            Optional[Document]: 文档对象，如果不存在或不在指定站点中则返回None
        """
        document = None
        
        # 根据提供的参数查找文档
        if url:
            document = get_document_by_url(url)
        elif content_hash:
            document = get_document_by_hash(content_hash)
        
        # 如果找到文档且指定了站点ID，验证文档是否在站点中
        if document and site_id:
            if not check_document_in_site(document.url, site_id):
                self.logger.debug(f"文档 {document.url} 不在站点 {site_id} 中")
                return None
        
        return document
    
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
        if not site_id:
            self.logger.warning("获取站点文档时未提供站点ID")
            return []
            
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
    
    def delete_document(self, url: str, site_id: Optional[str] = None) -> bool:
        """
        删除文档
        
        Args:
            url: 文档URL
            site_id: 站点ID，如果提供则仅从该站点中移除文档，否则完全删除文档
            
        Returns:
            bool: 是否成功删除
        """
        # 获取文档
        document = get_document_by_url(url)
        if not document:
            self.logger.warning(f"要删除的文档不存在: {url}")
            return False
        
        try:
            # 如果指定了站点ID，仅从该站点中移除文档
            if site_id:
                result = document.remove_from_site(site_id)
                # 检查文档是否还属于其他站点
                if result and not document.get_site_ids():
                    # 如果文档已不属于任何站点，完全删除它
                    return delete_document(url)
                return result
            else:
                # 完全删除文档
                return delete_document(url)
        except Exception as e:
            self.logger.error(f"删除文档时发生错误: {str(e)}")
            return False
    
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
    
    def check_exists(self, url: str, site_id: Optional[str] = None, content_hash: Optional[str] = None) -> Tuple[bool, Optional[Document], str]:
        """
        检查文档是否存在
        
        Args:
            url: 文档URL
            site_id: 站点ID，如果提供则还检查文档是否在特定站点中
            content_hash: 内容哈希值（可选）
            
        Returns:
            Tuple[bool, Optional[Document], str]: 
                - 是否存在
                - 存在的文档对象（如果有）
                - 操作类型（'new'/'edit'/'skip'/'new_site'）
        """
        return check_document_exists(url, site_id, content_hash)
    
    def add_document_to_site(self, document_id: int, site_id: str) -> bool:
        """
        将文档添加到站点
        
        Args:
            document_id: 文档ID
            site_id: 站点ID
            
        Returns:
            bool: 是否成功添加
        """
        if not site_id:
            self.logger.error("添加文档到站点时未提供站点ID")
            return False
            
        return add_document_to_site(document_id, site_id)
    
    def remove_document_from_site(self, document_id: int, site_id: str) -> bool:
        """
        从站点中移除文档
        
        Args:
            document_id: 文档ID
            site_id: 站点ID
            
        Returns:
            bool: 是否成功移除
        """
        if not site_id:
            self.logger.error("从站点移除文档时未提供站点ID")
            return False
            
        return remove_document_from_site(document_id, site_id)
    
    def get_document_sites(self, document_id: int) -> List[str]:
        """
        获取文档关联的所有站点ID
        
        Args:
            document_id: 文档ID
            
        Returns:
            List[str]: 站点ID列表
        """
        return get_document_sites(document_id)
    
    def copy_document_to_site(self, url: str, site_id: str) -> bool:
        """
        将现有文档复制到另一个站点
        
        Args:
            url: 文档URL
            site_id: 目标站点ID
            
        Returns:
            bool: 是否成功复制
        """
        if not site_id:
            self.logger.error("复制文档到站点时未提供站点ID")
            return False
            
        document = self.get_document(url=url)
        if not document:
            self.logger.error(f"要复制的文档不存在: {url}")
            return False
            
        try:
            # 检查文档是否已在目标站点中
            if check_document_in_site(url, site_id):
                self.logger.info(f"文档 {url} 已在站点 {site_id} 中，无需复制")
                return True
                
            document.add_to_site(site_id)
            self.logger.info(f"文档已复制到站点 {site_id}: {url}")
            return True
        except Exception as e:
            self.logger.error(f"复制文档到站点时发生错误: {str(e)}")
            return False
            
    def is_document_in_site(self, url: str, site_id: str) -> bool:
        """
        检查文档是否在特定站点中
        
        Args:
            url: 文档URL
            site_id: 站点ID
            
        Returns:
            bool: 文档是否在站点中
        """
        if not url or not site_id:
            return False
            
        return check_document_in_site(url, site_id)
        
    def get_document_in_site(self, url: str, site_id: str) -> Optional[Document]:
        """
        获取站点中的特定文档
        
        Args:
            url: 文档URL
            site_id: 站点ID
            
        Returns:
            Optional[Document]: 文档对象，如果文档不存在或不在站点中则返回None
        """
        return self.get_document(url=url, site_id=site_id)
    