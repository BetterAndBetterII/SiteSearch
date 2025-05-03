import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

import dotenv
from llama_index.core import Document, Settings, VectorStoreIndex, StorageContext
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding

from llama_index.llms.openai_like import OpenAILike
from llama_index.storage.docstore.redis import RedisDocumentStore
from llama_index.postprocessor.jinaai_rerank import JinaRerank

from llama_index.vector_stores.milvus import MilvusVectorStore
from .custom.bgem3_sparse import BGEM3SparseEmbeddingFunction
from .custom.siliconflow_embeddings import SiliconFlowEmbedding

# 加载环境变量
dotenv.load_dotenv("/root/workspace/SiteSearch/.env", override=True)

# 配置LLM设置
Settings.llm = OpenAILike(
    api_key=os.getenv("OPENAI_API_KEY"),
    api_base=os.getenv("OPENAI_BASE_URL"),
    model="gpt-4o-mini",
    is_chat_model=True,
    max_retries=64,
)

# 配置Embedding设置
Settings.embed_model = SiliconFlowEmbedding(
    api_key=os.getenv("EMBEDDING_API_KEY"),
    base_url=f"{os.getenv('EMBEDDING_BASE_URL')}/embeddings",
    model="bge-m3",
    timeout=30,
    max_retries=64,
    dimensions=int(os.getenv("EMB_DIMENSIONS", 1536)),
)


class DataIndexer:
    """站点索引管理器，支持按site_id进行命名空间管理"""
    
    def __init__(
        self, 
        redis_uri: str, 
        milvus_uri: str, 
        site_id: str,
        redis_namespace_prefix: str = "sitesearch",
        milvus_collection_prefix: str = "sitesearch",
        chunk_size: int = 1024,
        chunk_overlap: int = 256,
        similarity_metric: str = "cosine",
        dim: int = None,
        enable_sparse: bool = True,
        sparse_embedding_function = None,
        embed_model = None
    ):
        """
        初始化站点索引管理器
        
        Args:
            redis_uri: Redis连接URI
            milvus_uri: Milvus连接URI
            site_id: 站点ID，用于命名空间隔离
            redis_namespace_prefix: Redis命名空间前缀，默认为"sitesearch"
            milvus_collection_prefix: Milvus集合前缀，默认为"sitesearch"
            chunk_size: 文本分块大小，默认为512
            chunk_overlap: 文本分块重叠大小，默认为128
            similarity_metric: 相似度度量方式，默认为"cosine"
            dim: 向量维度，默认使用环境变量设置
            enable_sparse: 是否启用稀疏向量，默认为True
            sparse_embedding_function: 稀疏向量嵌入函数，默认使用BGEM3
            embed_model: 嵌入模型，默认使用Settings中配置的模型
        """
        if not re.match(r'^[a-zA-Z0-9_]+$', site_id):
            site_id = re.sub(r'[^a-zA-Z0-9_]', '_', site_id)
        self.site_id = site_id
        self.redis_namespace = f"{redis_namespace_prefix}:{site_id}:docs"
        # collection name can only contain numbers, letters and underscores
        self.milvus_collection = f"{milvus_collection_prefix}_{site_id}_vectors"
        
        # 解析URIs
        import urllib.parse
        print(f"redis_uri: {redis_uri}")
        print(f"milvus_uri: {milvus_uri}")
        redis_parsed = urllib.parse.urlparse(redis_uri)
        milvus_parsed = urllib.parse.urlparse(milvus_uri)
        
        # 初始化Redis文档存储
        self.doc_store = RedisDocumentStore.from_host_and_port(
            host=redis_parsed.hostname,
            port=redis_parsed.port,
            namespace=self.redis_namespace,
        )
        
        # 使用传入的稀疏向量嵌入函数或默认值
        sparse_func = sparse_embedding_function or BGEM3SparseEmbeddingFunction()
        
        # 使用传入的维度或环境变量
        vector_dim = dim or int(os.getenv("EMB_DIMENSIONS", 1536))
        
        # 初始化Milvus向量存储
        self.vector_store = MilvusVectorStore(
            uri="",  # 设置为空字符串避免使用本地文件
            host=milvus_parsed.hostname,
            port=milvus_parsed.port,
            db_name=milvus_parsed.path[1:],
            collection_name=self.milvus_collection,
            dim=vector_dim,
            similarity_metric=similarity_metric,
            enable_sparse=enable_sparse,
            sparse_embedding_function=sparse_func,
            index_config={
                "metric_type": "COSINE",
                "index_type": "HNSW",
                "params": {"M": 32, "efConstruction": 200}
            },
            search_config={"ef": 512}
        )
        
        # 初始化存储上下文
        self.storage_context = StorageContext.from_defaults(
            docstore=self.doc_store,
            vector_store=self.vector_store,
        )
        
        # 初始化向量索引
        self.index = VectorStoreIndex.from_vector_store(
            vector_store=self.vector_store,
            storage_context=self.storage_context,
        )
        
        # 使用传入的嵌入模型或全局设置
        self.embed_model = embed_model or Settings.embed_model
        
        # 初始化摄入管道
        self.pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                ),
                self.embed_model,
            ],
            vector_store=self.vector_store,
            docstore=self.doc_store,
            disable_cache=True,
        )

    async def add_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """
        添加文档到索引
        
        Args:
            documents: 文档列表，每个文档包含流转数据的所有字段
            
        Returns:
            List[str]: 文档ID列表
        """
        docs = []
        doc_ids = []
        
        for doc_data in documents:
            # 生成文档ID
            doc_id = f"{self.site_id}:{doc_data['content_hash']}"
            doc_ids.append(doc_id)
            
            # 创建Document对象
            doc = Document(
                text=doc_data['clean_content'],
                id_=doc_id,
                metadata={
                    "site_id": self.site_id,
                    "url": doc_data.get('url'),
                    "title": doc_data.get('metadata', {}).get('title'),
                    "mimetype": doc_data.get('mimetype'),
                    "content_hash": doc_data['content_hash'],
                }
            )
            docs.append(doc)
        
        # 执行文档摄入
        await self.pipeline.arun(documents=docs)
        return doc_ids

    async def aremove_documents(self, content_hashs: str) -> bool:
        """
        从索引中删除文档
        
        Args:
            doc_ids: 要删除的文档ID列表
        """
        try:
            for content_hash in content_hashs:
                await self.index.adelete_ref_doc(
                    ref_doc_id=f"{self.site_id}:{content_hash}",
                    delete_from_docstore=True
                )
            await self.doc_store.adelete_document(f"{self.site_id}:{content_hash}")
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False
        return True
    
    def remove_documents(self, content_hashs: List[str]) -> bool:
        """
        从索引中删除文档
        
        Args:
            doc_ids: 要删除的文档ID列表
        """
        try:
            for content_hash in content_hashs:
                self.index.delete_ref_doc(
                    ref_doc_id=f"{self.site_id}:{content_hash}",
                    delete_from_docstore=True
                )
            self.doc_store.delete_document(f"{self.site_id}:{content_hash}")
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False
        return True

    async def aremove_documents_by_id(self, doc_ids: List[str]) -> bool:
        """
        从索引中删除文档
        
        Args:
            doc_ids: 要删除的文档ID列表
        """
        try:
            for doc_id in doc_ids:
                await self.index.adelete_ref_doc(
                    ref_doc_id=doc_id,
                    delete_from_docstore=True
                )
            await self.doc_store.adelete_document(doc_ids)
        except Exception as e:
            print(f"删除文档失败: {e}")
            return False
        return True

    async def remove_all_documents(self) -> None:
        """删除该站点的所有文档"""
        all_docs = self.doc_store.docs
        for doc_id in all_docs.keys():
            if doc_id.startswith(f"{self.site_id}:"):
                await self.aremove_documents([doc_id])

    async def get_document_by_content_hash(self, content_hash: str) -> Optional[Document]:
        """
        获取指定文档
        
        Args:
            content_hash: 文档内容hash
            
        Returns:
            Optional[Document]: 文档对象，如果不存在则返回None
        """
        try:
            return await self.doc_store.aget_document(f"{self.site_id}:{content_hash}")
        except KeyError:
            return None
        
    async def get_document_by_id(self, doc_id: str) -> Optional[Document]:
        """
        获取指定文档
        
        Args:
            doc_id: 文档ID

        Returns:
            Optional[Document]: 文档对象，如果不存在则返回None
        """
        try:
            return await self.doc_store.aget_document(doc_id)
        except KeyError:
            return None
        except ValueError as e:
            print(f"获取文档失败: {e}")
            return None

    async def list_documents(self) -> List[Dict[str, Any]]:
        """
        列出该站点的所有文档
        
        Returns:
            List[Dict[str, Any]]: 文档列表
        """
        all_docs = self.doc_store.docs
        site_docs = []
        
        for doc_id, doc in all_docs.items():
            if doc_id.startswith(f"{self.site_id}:"):
                site_docs.append({
                    "id": doc_id,
                    "metadata": doc.metadata,
                    "text_preview": doc.text[:200],
                })
        
        return site_docs

    async def update_document(self, content_hash: str, new_content: str) -> bool:
        """
        更新文档内容
        
        Args:
            content_hash: 文档内容hash
            new_content: 新的文档内容
            
        Returns:
            bool: 更新是否成功
        """
        try:
            old_doc = await self.get_document_by_content_hash(content_hash)   
            if not old_doc:
                return False
                
            # 创建新文档，保留原有元数据
            new_doc = Document(
                text=new_content,
                id_=f"{self.site_id}:{content_hash}",
                metadata={
                    **old_doc.metadata,
                    "updated_at": datetime.now().isoformat()
                }
            )
            
            # 删除旧文档并添加新文档
            await self.aremove_documents([f"{self.site_id}:{content_hash}"])
            await self.pipeline.arun(documents=[new_doc])
            return True
        except Exception:
            return False

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rerank: bool = True,
        rerank_top_k: int = 10,
        similarity_cutoff: float = 0.6,
        search_kwargs: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的最大文档数量
            rerank: 是否进行重排序
            rerank_top_k: 重排序返回的最大文档数量
            similarity_cutoff: 相似度阈值
            search_kwargs: 搜索的额外参数
            
        Returns:
            List[Dict[str, Any]]: 检索结果列表
        """
        from llama_index.core import QueryBundle
        from llama_index.core.indices.vector_store import VectorIndexRetriever
        from llama_index.core.postprocessor import SimilarityPostprocessor
        from llama_index.core.vector_stores.types import VectorStoreQueryMode
        
        # 合并默认参数和传入的搜索参数
        search_params = {}
        if search_kwargs:
            search_params.update(search_kwargs)
        
        # 创建检索器
        vector_retriever = VectorIndexRetriever(
            index=self.index,
            similarity_top_k=top_k,
            vector_store_query_mode=VectorStoreQueryMode.HYBRID,
            **search_params
        )
        
        # 执行检索
        qb = QueryBundle(query)
        nodes = await vector_retriever.aretrieve(qb)

        print(f"Nodes: {nodes}")
        
        # 重排序处理
        if rerank:
            reranker = JinaRerank(
                base_url=os.getenv("RERANKER_BASE_URL"),
                model="bge-reranker-v2-m3",
                api_key=os.getenv("RERANKER_API_KEY"),
                top_n=rerank_top_k,
            )
            nodes = reranker.postprocess_nodes(nodes, qb)
            nodes = SimilarityPostprocessor(
                similarity_cutoff=similarity_cutoff
            ).postprocess_nodes(nodes)

            print(f"Reranked Nodes: {nodes}")
        
        # 格式化结果
        results = []
        for node in nodes:
            doc = await self.get_document_by_id(node.node.ref_doc_id)
            if doc:
                results.append({
                    "id": node.node.ref_doc_id,
                    "text": node.node.text,
                    "score": node.score if hasattr(node, 'score') else None,
                    "metadata": doc.metadata
                })
            else:
                print(f"获取文档失败: {node.node.ref_doc_id}")
                # 获取文档失败，则从索引中删除该文档
                await self.aremove_documents_by_id([node.node.ref_doc_id])
        
        return results
    
    async def batch_add_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 32
    ) -> List[str]:
        """
        批量添加文档
        
        Args:
            documents: 文档列表
            batch_size: 批处理大小
            
        Returns:
            List[str]: 文档ID列表
        """
        all_doc_ids = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            doc_ids = await self.add_documents(batch)
            all_doc_ids.extend(doc_ids)
            
        return all_doc_ids

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        all_docs = self.doc_store.docs
        site_docs = [
            doc for doc_id, doc in all_docs.items()
            if doc_id.startswith(f"{self.site_id}:")
        ]
        
        return {
            "site_id": self.site_id,
            "total_documents": len(site_docs),
            "total_tokens": sum(len(doc.text.split()) for doc in site_docs),
            "average_document_length": sum(len(doc.text.split()) for doc in site_docs) / len(site_docs) if site_docs else 0,
            "redis_namespace": self.redis_namespace,
            "milvus_collection": self.milvus_collection,
        }

class IndexerFactory:
    """索引管理器工厂，用于创建和管理站点索引实例"""
    
    _instances: Dict[str, DataIndexer] = {}
    
    @classmethod
    def get_instance(
        cls,
        site_id: str,
        redis_uri: str = os.getenv("REDIS_URL"),
        milvus_uri: str = os.getenv("MILVUS_URI"),
        use_cache: bool = False,
        **kwargs
    ) -> DataIndexer:
        """
        获取数据索引管理器实例，如果不存在则创建新实例
        
        Args:
            site_id: 站点ID
            redis_uri: Redis连接URI
            milvus_uri: Milvus连接URI
            use_cache: 是否使用缓存的实例，默认不使用缓存
            **kwargs: 传递给DataIndexer的其他参数，例如：
                - redis_namespace_prefix: Redis命名空间前缀
                - milvus_collection_prefix: Milvus集合前缀
                - chunk_size: 文本分块大小
                - chunk_overlap: 文本分块重叠大小
                - similarity_metric: 相似度度量方式
                - dim: 向量维度
                - enable_sparse: 是否启用稀疏向量
                - sparse_embedding_function: 稀疏向量嵌入函数
                - embed_model: 嵌入模型
            
        Returns:
            DataIndexer: 数据索引管理器实例
        """
        # 如果使用缓存且实例已存在，则返回缓存的实例
        cache_key = f"{site_id}:{redis_uri}:{milvus_uri}"
        if use_cache and cache_key in cls._instances:
            return cls._instances[cache_key]
            
        # 创建新实例
        indexer = DataIndexer(
            redis_uri=redis_uri,
            milvus_uri=milvus_uri,
            site_id=site_id,
            **kwargs
        )
        
        # 如果使用缓存，则保存实例
        if use_cache:
            cls._instances[cache_key] = indexer
            
        return indexer
        
    @classmethod
    def clear_cache(cls):
        """清除缓存的实例"""
        cls._instances.clear()