"""
存储模块的工具函数
提供文档存储、检索和管理的辅助函数
"""

import logging
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from django.db import transaction, IntegrityError, models
from django.db.models import Q

from .models import Document, CrawlHistory, SiteDocument

logger = logging.getLogger('storage')

def generate_content_hash(content: str) -> str:
    """
    生成内容的哈希值，用于去重和变更检测
    
    Args:
        content: 页面内容
        
    Returns:
        str: 内容的SHA-256哈希值
    """
    if not content:
        return ""
    
    # 使用SHA-256算法计算哈希值
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def check_document_exists(url: str, site_id, content_hash: Optional[str] = None) -> Tuple[bool, Optional[Document], str]:
    """
    检查文档是否已存在，并确定操作类型
    
    Args:
        url: 文档URL
        site_id: 站点ID，如果提供则还检查文档是否在特定站点中
        content_hash: 内容哈希值，如果不提供则只检查URL
        
    Returns:
        Tuple[bool, Optional[Document], str]: 
            - 是否存在
            - 存在的文档对象（如果有）
            - 操作类型（'new'/'edit'/'skip'/'new_site'）
    """
    try:
        # 先按URL查找，这是主要的唯一性检查
        existing_doc = Document.objects.filter(url=url).first()
        
        # 如果URL不存在但是有内容哈希，可以尝试按内容哈希查找（可能是URL变化但内容相同的情况）
        if not existing_doc and content_hash:
            existing_doc = Document.objects.filter(content_hash=content_hash).first()
        
        if not existing_doc:
            return False, None, "new"
        
        # 如果提供了站点ID，检查文档是否已在该站点中
        if site_id and existing_doc:
            site_exists = SiteDocument.objects.filter(document=existing_doc, site_id=site_id).exists()
            # 如果文档存在但不在指定站点中，返回'new_site'类型
            if not site_exists:
                return True, existing_doc, "new_site"
        
        # 如果提供了内容哈希值，检查内容是否变化
        if content_hash and existing_doc.content_hash != content_hash:
            return True, existing_doc, "edit"
        
        # URL存在且内容未变化（或未提供内容哈希值）
        return True, existing_doc, "skip"
    
    except Exception as e:
        logger.error(f"检查文档存在性时出错: {str(e)}")
        return False, None, "error"

@transaction.atomic
def store_document(data: Dict[str, Any]) -> Tuple[Document, str]:
    """
    存储文档到数据库
    
    Args:
        data: 文档数据字典
        
    Returns:
        Tuple[Document, str]: 存储的文档对象和操作类型
    """
    # 确保URL存在
    if 'url' not in data:
        raise ValueError("文档数据缺少URL字段")
    
    # 确保内容存在
    if 'content' not in data:
        raise ValueError("文档数据缺少content字段")
    
    # 生成内容哈希（如果不存在）
    if 'content_hash' not in data or not data['content_hash']:
        data['content_hash'] = generate_content_hash(data['content'])
    
    # 获取站点ID（可能存在多个）
    site_ids = []
    if 'site_id' in data and data['site_id']:
        site_ids.append(data['site_id'])
    if 'site_ids' in data and data['site_ids']:
        # 合并site_ids列表，并确保唯一性
        site_ids.extend([sid for sid in data['site_ids'] if sid not in site_ids])
    
    # 确保至少有一个站点ID
    if not site_ids:
        logger.warning(f"文档 {data['url']} 没有提供站点ID")
    
    # 使用主站点ID进行存在性检查
    primary_site_id = site_ids[0] if site_ids else None
    exists, existing_doc, operation = check_document_exists(data['url'], primary_site_id, data['content_hash'])
    
    try:
        # 处理不同操作类型
        if operation == "new":
            # 创建新文档
            document = Document.from_crawler_data(data)
            document.save()
            
            # 添加站点关联
            for site_id in site_ids:
                document.add_to_site(site_id)
            
            # 创建新的历史记录
            history = CrawlHistory.from_document(document, "new")
            history.save()
            
            logger.info(f"新文档已存储: {document.url}")
            return document, "new"
        
        elif operation == "new_site":
            # 文档存在但需要添加到新站点
            for site_id in site_ids:
                existing_doc.add_to_site(site_id)
            
            logger.info(f"已将文档 {existing_doc.url} 添加到新站点")
            return existing_doc, "new_site"
        
        elif operation == "edit":
            # 对于已存在但内容已更新的文档
            # 更新版本号
            new_version = existing_doc.version + 1
            
            # 更新现有文档记录，而不是创建新记录
            existing_doc.content = data['content']
            existing_doc.clean_content = data.get('clean_content')
            existing_doc.status_code = data.get('status_code', existing_doc.status_code)
            existing_doc.headers = data.get('headers', existing_doc.headers)
            existing_doc.timestamp = data.get('timestamp', int(datetime.now().timestamp()))
            existing_doc.links = data.get('links', existing_doc.links)
            existing_doc.mimetype = data.get('mimetype', existing_doc.mimetype)
            existing_doc.content_hash = data['content_hash']
            existing_doc.version = new_version
            existing_doc.index_operation = "edit"
            
            # 更新元数据
            metadata = data.get('metadata', {})
            if metadata:
                existing_doc.set_metadata(metadata)
                
            # 保存更新后的文档
            existing_doc.save()
            
            # 添加到新站点（如果有）
            for site_id in site_ids:
                existing_doc.add_to_site(site_id)
            
            # 创建历史记录
            history = CrawlHistory.from_document(existing_doc, "edit")
            history.save()
            
            logger.info(f"文档已更新: {existing_doc.url} (v{new_version})")
            return existing_doc, "edit"
        
        elif operation == "skip":
            # 文档内容未变化，仅更新站点关联
            # 添加到新站点（如果有）
            for site_id in site_ids:
                existing_doc.add_to_site(site_id)
            
            logger.info(f"文档 {data['url']} 内容未变化，已更新站点关联")
            return existing_doc, "skip"
    
    except IntegrityError as e:
        logger.error(f"存储文档时发生完整性错误: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"存储文档时发生错误: {str(e)}")
        raise
    
    return existing_doc, operation

def get_document_by_url(url: str) -> Optional[Document]:
    """
    根据URL获取文档
    
    Args:
        url: 文档URL
        
    Returns:
        Optional[Document]: 文档对象，如果不存在则返回None
    """
    try:
        return Document.objects.filter(url=url).first()
    except Exception as e:
        logger.error(f"获取文档时发生错误: {str(e)}")
        return None

def get_document_by_hash(content_hash: str) -> Optional[Document]:
    """
    根据内容哈希获取文档
    
    Args:
        content_hash: 内容哈希值
        
    Returns:
        Optional[Document]: 文档对象，如果不存在则返回None
    """
    try:
        return Document.objects.filter(content_hash=content_hash).first()
    except Exception as e:
        logger.error(f"根据哈希获取文档时发生错误: {str(e)}")
        return None

def get_documents_by_site(site_id: str, limit: int = 100, offset: int = 0) -> List[Document]:
    """
    获取指定站点的所有文档
    
    Args:
        site_id: 站点ID
        limit: 结果数量限制
        offset: 结果偏移量
        
    Returns:
        List[Document]: 文档对象列表
    """
    try:
        if not site_id:
            logger.warning("未提供站点ID，返回空列表")
            return []
            
        # 使用关联表查询特定站点的文档
        site_docs = SiteDocument.objects.filter(site_id=site_id).select_related('document')
        documents = [sd.document for sd in site_docs.order_by('-created_at')[offset:offset+limit]]
        return documents
    except Exception as e:
        logger.error(f"获取站点文档时发生错误: {str(e)}")
        return []

def get_pending_index_documents(limit: int = 50) -> List[Document]:
    """
    获取待索引的文档
    
    Args:
        limit: 结果数量限制
        
    Returns:
        List[Document]: 待索引的文档列表
    """
    try:
        return list(Document.objects.filter(is_indexed=False).order_by('created_at')[:limit])
    except Exception as e:
        logger.error(f"获取待索引文档时发生错误: {str(e)}")
        return []

def mark_document_indexed(document_id: int, indexed: bool = True) -> bool:
    """
    标记文档为已索引
    
    Args:
        document_id: 文档ID
        indexed: 是否已索引
        
    Returns:
        bool: 操作是否成功
    """
    try:
        document = Document.objects.get(id=document_id)
        document.is_indexed = indexed
        document.save(update_fields=['is_indexed', 'updated_at'])
        return True
    except Document.DoesNotExist:
        logger.error(f"文档ID {document_id} 不存在")
        return False
    except Exception as e:
        logger.error(f"标记文档索引状态时发生错误: {str(e)}")
        return False

def delete_document(url: str) -> bool:
    """
    删除文档
    
    Args:
        url: 文档URL
        
    Returns:
        bool: 是否成功删除
    """
    try:
        document = Document.objects.filter(url=url).first()
        if document:
            # 创建一个"删除"类型的历史记录
            history = CrawlHistory.from_document(document, "delete")
            history.save()
            
            # 删除文档（会级联删除站点关联）
            document.delete()
            logger.info(f"文档已删除: {url}")
            return True
        else:
            logger.warning(f"要删除的文档不存在: {url}")
            return False
    except Exception as e:
        logger.error(f"删除文档时发生错误: {str(e)}")
        return False

def add_document_to_site(document_id: int, site_id: str) -> bool:
    """
    将文档添加到站点
    
    Args:
        document_id: 文档ID
        site_id: 站点ID
        
    Returns:
        bool: 是否成功添加
    """
    try:
        document = Document.objects.get(id=document_id)
        document.add_to_site(site_id)
        return True
    except Document.DoesNotExist:
        logger.error(f"文档ID {document_id} 不存在")
        return False
    except Exception as e:
        logger.error(f"将文档添加到站点时发生错误: {str(e)}")
        return False

def remove_document_from_site(document_id: int, site_id: str) -> bool:
    """
    从站点中移除文档
    
    Args:
        document_id: 文档ID
        site_id: 站点ID
        
    Returns:
        bool: 是否成功移除
    """
    try:
        document = Document.objects.get(id=document_id)
        return document.remove_from_site(site_id)
    except Document.DoesNotExist:
        logger.error(f"文档ID {document_id} 不存在")
        return False
    except Exception as e:
        logger.error(f"从站点移除文档时发生错误: {str(e)}")
        return False

def get_document_sites(document_id: int) -> List[str]:
    """
    获取文档关联的所有站点ID
    
    Args:
        document_id: 文档ID
        
    Returns:
        List[str]: 站点ID列表
    """
    try:
        document = Document.objects.get(id=document_id)
        return document.get_site_ids()
    except Document.DoesNotExist:
        logger.error(f"文档ID {document_id} 不存在")
        return []
    except Exception as e:
        logger.error(f"获取文档站点时发生错误: {str(e)}")
        return []

def get_document_history(url: str) -> List[CrawlHistory]:
    """
    获取文档的历史记录
    
    Args:
        url: 文档URL
        
    Returns:
        List[CrawlHistory]: 历史记录列表
    """
    try:
        return list(CrawlHistory.objects.filter(url=url).order_by('-created_at'))
    except Exception as e:
        logger.error(f"获取文档历史时发生错误: {str(e)}")
        return []

def search_documents(query: str, site_id: Optional[str] = None, limit: int = 50) -> List[Document]:
    """
    简单搜索文档（基于数据库，非向量搜索）
    
    Args:
        query: 搜索查询
        site_id: 限制在特定站点内搜索
        limit: 结果数量限制
        
    Returns:
        List[Document]: 匹配的文档列表
    """
    try:
        # 构建查询条件
        conditions = Q(title__icontains=query) | Q(description__icontains=query) | Q(clean_content__icontains=query)
        
        # 如果指定了站点，获取该站点下的文档ID
        if site_id:
            # 先获取站点关联的所有文档ID
            doc_ids = SiteDocument.objects.filter(site_id=site_id).values_list('document_id', flat=True)
            
            # 如果没有找到任何文档ID，返回空列表
            if not doc_ids:
                logger.debug(f"站点 {site_id} 中没有找到任何文档")
                return []
                
            # 添加文档ID过滤条件
            conditions &= Q(id__in=doc_ids)
        
        # 执行查询
        return list(Document.objects.filter(conditions).order_by('-created_at')[:limit])
    except Exception as e:
        logger.error(f"搜索文档时发生错误: {str(e)}")
        return []

def get_storage_stats() -> Dict[str, Any]:
    """
    获取存储统计信息
    
    Returns:
        Dict[str, Any]: 存储统计信息
    """
    try:
        total_documents = Document.objects.count()
        indexed_documents = Document.objects.filter(is_indexed=True).count()
        pending_documents = Document.objects.filter(is_indexed=False).count()
        total_sites = SiteDocument.objects.values('site_id').distinct().count()
        
        # 获取每个站点的文档数量
        site_stats = {}
        for item in SiteDocument.objects.values('site_id').annotate(count=models.Count('document_id')):
            site_stats[item['site_id']] = item['count']
        
        # 获取文档类型统计
        mime_stats = {}
        for item in Document.objects.values('mimetype').annotate(count=models.Count('id')):
            mime_stats[item['mimetype']] = item['count']
        
        return {
            'total_documents': total_documents,
            'indexed_documents': indexed_documents,
            'pending_documents': pending_documents,
            'total_sites': total_sites,
            'site_stats': site_stats,
            'mime_types': mime_stats,
            'last_update': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"获取存储统计信息时发生错误: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def check_document_in_site(url: str, site_id: str) -> bool:
    """
    检查特定URL的文档是否在指定站点中
    
    Args:
        url: 文档URL
        site_id: 站点ID
        
    Returns:
        bool: 文档是否在指定站点中
    """
    try:
        if not url or not site_id:
            return False
            
        # 先查找文档
        document = Document.objects.filter(url=url).first()
        if not document:
            return False
            
        # 检查文档是否在指定站点中
        return SiteDocument.objects.filter(document=document, site_id=site_id).exists()
    except Exception as e:
        logger.error(f"检查文档是否在站点中时发生错误: {str(e)}")
        return False 