"""
搜索模块
实现基于向量索引的语义搜索功能
"""
import asyncio
import time
import logging
from typing import Dict, List, Any, Optional
from django.core.paginator import Paginator
from django.db.models import Q
from asgiref.sync import sync_to_async

from src.backend.sitesearch.indexer.index_manager import IndexerFactory
from src.backend.sitesearch.storage.models import Document as DBDocument, SiteDocument

# 添加性能监控日志配置
logger = logging.getLogger(__name__)

async def semantic_search_documents(
    query: str,
    filters: Dict[str, Any] = None,
    top_k: int = 5,
    page: int = 1,
    similarity_cutoff: float = 0.6,
    rerank: bool = True,
    rerank_top_k: int = 10,
    index_options: Dict[str, Any] = None,
    retrieve_options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    执行语义搜索，从向量索引中检索相关文档
    
    Args:
        query: 搜索查询
        filters: 过滤条件，包含site_id等
        top_k: 返回的最大文档数量
        page: 页码
        similarity_cutoff: 相似度阈值
        rerank: 是否使用重排序
        rerank_top_k: 重排序返回的最大文档数量
        index_options: 索引器选项，传递给IndexerFactory.get_instance
        retrieve_options: 检索选项，传递给DataIndexer.retrieve
        
    Returns:
        Dict[str, Any]: 搜索结果，包含结果列表和统计信息
    """
    # 记录总体开始时间
    total_start_time = time.time()
    performance_metrics = {}
    
    logger.info(f"Starting semantic search - Query: '{query}' | Filters: {filters}")
    
    if not query:
        return {
            "results": [],
            "total_count": 0,
            "page": page,
            "page_size": top_k
        }
    
    # 阶段1: 参数处理和准备
    prep_start_time = time.time()
    
    # 获取站点ID（如果提供）
    site_id = filters.get('site_id') if filters else None
    site_ids = filters.get('site_ids') if filters else None
    
    # 准备索引器选项
    idx_options = {}
    if index_options:
        idx_options.update(index_options)
    
    # 初始化索引管理器，可以传入更多自定义参数
    if site_id:
        site_ids = [site_id]
    
    performance_metrics['preparation'] = (time.time() - prep_start_time) * 1000
    
    final_results = []
    vector_search_total_time = 0
    db_query_total_time = 0

    for current_site_id in site_ids:
        # 阶段2: 获取索引器实例
        indexer_start_time = time.time()
        
        data_indexer = IndexerFactory.get_instance(
            site_id=current_site_id or "global",
            **idx_options
        )
        
        indexer_time = (time.time() - indexer_start_time) * 1000
        vector_search_total_time += indexer_time
        
        # 阶段3: 向量检索
        vector_start_time = time.time()
        
        # 准备检索选项
        rtr_options = {}
        if retrieve_options:
            rtr_options.update(retrieve_options)
        
        # 执行向量检索，可以传入更多自定义参数
        vector_results = await data_indexer.retrieve(
            query=query,
            top_k=top_k,  # 获取更多结果，以便后续过滤
            rerank=rerank,
            rerank_top_k=rerank_top_k,
            similarity_cutoff=similarity_cutoff,
            search_kwargs=rtr_options
        )
        
        vector_time = (time.time() - vector_start_time) * 1000
        vector_search_total_time += vector_time
        
        logger.info(f"Vector search for site {current_site_id}: {vector_time:.2f}ms, found {len(vector_results)} results")
        
        if not vector_results:
            continue
        
        # 阶段4: 提取内容哈希
        hash_extract_start_time = time.time()
        
        # 提取文档ID列表（去除site_id前缀）
        content_hash_list = []
        for result in vector_results:
            # 从节点ID中提取content_hash（格式为site_id:content_hash）
            full_id = result.get('id', '')
            if ':' in full_id:
                content_hash = full_id.split(':', 1)[1]
                content_hash_list.append(content_hash)
        
        hash_extract_time = (time.time() - hash_extract_start_time) * 1000
        
        # 查询数据库获取完整文档信息
        if not content_hash_list:
            continue
        
        # 阶段5: 数据库查询
        db_start_time = time.time()
        
        # 构建查询条件
        db_documents = {}
        doc_count = 0
        async for doc in DBDocument.objects.filter(content_hash__in=content_hash_list):
            doc_count += 1
            # 如果提供了site_id，确保文档属于该站点
            if current_site_id:
                site_ids_for_doc = await sync_to_async(doc.get_site_ids)()
                if current_site_id not in site_ids_for_doc:
                    continue
            db_documents[doc.content_hash] = doc
        
        db_time = (time.time() - db_start_time) * 1000
        db_query_total_time += db_time
        
        logger.info(f"DB query for site {current_site_id}: {db_time:.2f}ms, queried {doc_count} docs, matched {len(db_documents)} docs")
        
        # 阶段6: 结果构建
        result_build_start_time = time.time()
        
        # 构建最终结果，保留向量检索的顺序
        for result in vector_results:
            full_id = result.get('id', '')
            if ':' in full_id:
                content_hash = full_id.split(':', 1)[1]
                db_doc = db_documents.get(content_hash)
                
                if db_doc and (not filters.get('mimetype') or db_doc.mimetype == filters.get('mimetype')):
                    # 获取节点内容（用于摘要显示）
                    snippet = result.get('text', '')
                    
                    # 构建结果项
                    final_results.append({
                        'id': db_doc.id,
                        'url': db_doc.url,
                        'title': db_doc.title or '无标题',
                        'description': db_doc.description or '',
                        'content': snippet,  # 使用向量检索返回的节点内容作为摘要
                        'mimetype': db_doc.mimetype,
                        'content_hash': db_doc.content_hash,
                        'created_at': db_doc.created_at.isoformat(),
                        'updated_at': db_doc.updated_at.isoformat(),
                        'timestamp': db_doc.timestamp,
                        'score': result.get('score', 0.0),
                        'site_ids': await sync_to_async(db_doc.get_site_ids)(),
                        'highlights': {
                            'title': db_doc.title or '无标题',
                            'description': db_doc.description or '',
                            'content': snippet
                        }
                    })
        
        result_build_time = (time.time() - result_build_start_time) * 1000
        
        logger.info(f"Result building for site {current_site_id}: {result_build_time:.2f}ms, built {len(final_results)} results")
    
    # 阶段7: 分页处理
    pagination_start_time = time.time()
    
    # 应用分页
    paginator = Paginator(final_results, top_k)
    page_obj = paginator.get_page(page)
    
    pagination_time = (time.time() - pagination_start_time) * 1000
    
    # 计算总耗时
    total_time = (time.time() - total_start_time) * 1000
    
    # 记录性能指标
    performance_metrics.update({
        'vector_search_total': vector_search_total_time,
        'db_query_total': db_query_total_time,
        'pagination': pagination_time,
        'total': total_time
    })
    
    # 输出详细性能日志
    logger.info(f"Semantic Search Internal Performance - Query: '{query}'")
    logger.info(f"  ├─ Preparation: {performance_metrics['preparation']:.2f}ms")
    logger.info(f"  ├─ Vector Search Total: {performance_metrics['vector_search_total']:.2f}ms")
    logger.info(f"  ├─ DB Query Total: {performance_metrics['db_query_total']:.2f}ms")
    logger.info(f"  ├─ Pagination: {performance_metrics['pagination']:.2f}ms")
    logger.info(f"  └─ Total Internal: {performance_metrics['total']:.2f}ms")
    logger.info(f"Final Results: {paginator.count} total documents, page {page}/{paginator.num_pages}")
    
    # 计算各阶段占比
    if total_time > 0:
        logger.info("Internal Performance Breakdown:")
        logger.info(f"  ├─ Vector Search: {(performance_metrics['vector_search_total']/performance_metrics['total']*100):.1f}%")
        logger.info(f"  ├─ Database Query: {(performance_metrics['db_query_total']/performance_metrics['total']*100):.1f}%")
        logger.info(f"  ├─ Pagination: {(performance_metrics['pagination']/performance_metrics['total']*100):.1f}%")
        logger.info(f"  └─ Preparation: {(performance_metrics['preparation']/performance_metrics['total']*100):.1f}%")
    
    return {
        "results": list(page_obj),
        "total_count": paginator.count,
        "page": page,
        "page_size": top_k
    }

def sync_semantic_search_documents(
    query: str,
    filters: Dict[str, Any] = None,
    top_k: int = 5,
    page: int = 1,
    similarity_cutoff: float = 0.6,
    rerank: bool = True,
    index_options: Dict[str, Any] = None,
    retrieve_options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    同步版本的语义搜索函数
    
    Args:
        query: 搜索查询
        filters: 过滤条件，包含site_id等
        top_k: 返回的最大文档数量
        page: 页码
        similarity_cutoff: 相似度阈值
        rerank: 是否使用重排序
        index_options: 索引器选项，传递给IndexerFactory.get_instance
        retrieve_options: 检索选项，传递给DataIndexer.retrieve
        
    Returns:
        Dict[str, Any]: 搜索结果，包含结果列表和统计信息
    """
    return asyncio.run(semantic_search_documents(
        query=query,
        filters=filters,
        top_k=top_k,
        page=page,
        similarity_cutoff=similarity_cutoff,
        rerank=rerank,
        index_options=index_options,
        retrieve_options=retrieve_options
    ))

def search_documents(
    query: str,
    filters: Dict[str, Any] = None,
    page: int = 1,
    page_size: int = 10,
    sort_by: str = 'relevance',
    search_options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    执行全文搜索，从数据库中检索相关文档
    
    Args:
        query: 搜索查询
        filters: 过滤条件，包含site_id、mimetype、created_at__gte、created_at__lte等
        page: 页码
        page_size: 每页结果数量
        sort_by: 排序方式（relevance, date, title）
        search_options: 额外的搜索选项
        
    Returns:
        Dict[str, Any]: 搜索结果，包含结果列表和统计信息
    """
    if not query:
        return {
            "results": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size
        }
    
    try:
        # 处理过滤器
        filter_conditions = {}
        site_id = None
        
        # 如果提供了额外的搜索选项，更新filter_conditions
        if search_options:
            filter_conditions.update(search_options.get('filter_conditions', {}))
        
        if filters:
            site_id = filters.get('site_id')
            
            # 处理MIME类型过滤
            if 'mimetype' in filters:
                filter_conditions['mimetype'] = filters['mimetype']
                
            # 处理日期范围过滤
            if 'created_at__gte' in filters:
                filter_conditions['created_at__gte'] = filters['created_at__gte']
                
            if 'created_at__lte' in filters:
                filter_conditions['created_at__lte'] = filters['created_at__lte']
        
        # 构建搜索条件
        search_conditions = Q(title__icontains=query) | Q(description__icontains=query) | Q(clean_content__icontains=query)
        
        # 如果提供了自定义搜索条件，与默认条件组合
        if search_options and 'search_conditions' in search_options:
            custom_conditions = search_options['search_conditions']
            if custom_conditions:
                search_conditions = search_conditions & custom_conditions
        
        # 如果指定了站点ID，获取该站点下的文档ID
        if site_id:
            doc_ids = SiteDocument.objects.filter(site_id=site_id).values_list('document_id', flat=True)
            if not doc_ids:
                return {
                    "results": [],
                    "total_count": 0,
                    "page": page,
                    "page_size": page_size
                }
            filter_conditions['id__in'] = doc_ids
        
        # 应用过滤条件
        documents = DBDocument.objects.filter(search_conditions, **filter_conditions)
        
        # 应用排序
        if sort_by == 'date':
            documents = documents.order_by('-created_at')
        elif sort_by == 'title':
            documents = documents.order_by('title')
        elif search_options and 'order_by' in search_options:
            # 使用自定义排序
            documents = documents.order_by(search_options['order_by'])
        # relevance默认为数据库返回顺序
        
        # 应用分页
        paginator = Paginator(documents, page_size)
        page_obj = paginator.get_page(page)
        
        # 构建结果
        results = []
        for doc in page_obj:
            # 提取简短内容作为摘要
            content_snippet = doc.clean_content[:300] if doc.clean_content else ""
            
            result_item = {
                'id': doc.id,
                'url': doc.url,
                'title': doc.title or '无标题',
                'description': doc.description or '',
                'content': content_snippet,
                'mimetype': doc.mimetype,
                'content_hash': doc.content_hash,
                'created_at': doc.created_at.isoformat(),
                'updated_at': doc.updated_at.isoformat(),
                'timestamp': doc.timestamp,
                'score': 1.0,  # 全文搜索没有具体得分
                'site_ids': doc.get_site_ids(),
                'highlights': {
                    'title': doc.title or '无标题',
                    'description': doc.description or '',
                    'content': content_snippet
                }
            }
            
            # 如果有自定义结果处理器，应用它
            if search_options and 'result_processor' in search_options:
                processor = search_options['result_processor']
                if callable(processor):
                    result_item = processor(result_item, doc)
            
            results.append(result_item)
        
        return {
            "results": results,
            "total_count": paginator.count,
            "page": page,
            "page_size": page_size
        }
        
    except Exception as e:
        import logging
        logging.error(f"全文搜索出错: {str(e)}")
        return {
            "results": [],
            "total_count": 0,
            "page": page,
            "page_size": page_size,
            "error": str(e)
        } 