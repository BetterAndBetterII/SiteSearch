import os
import hashlib
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

from .custom.milvus_vectorstore import MilvusVectorStore
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
    max_retries=32,
    dimensions=int(os.getenv("EMB_DIMENSIONS", 1536)),
)

# 配置Reranker设置
Settings.reranker = JinaRerank(
    base_url=os.getenv("RERANKER_BASE_URL"),
    model="bge-reranker-v2-m3",
    api_key=os.getenv("RERANKER_API_KEY"),
    top_n=10,
)

class DataIndexer:
    """站点索引管理器，支持按site_id进行命名空间管理"""
    
    def __init__(self, redis_uri: str, milvus_uri: str, site_id: str):
        """
        初始化站点索引管理器
        
        Args:
            redis_uri: Redis连接URI
            milvus_uri: Milvus连接URI
            site_id: 站点ID，用于命名空间隔离
        """
        self.site_id = site_id
        self.redis_namespace = f"sitesearch:{site_id}:docs"
        self.milvus_collection = f"sitesearch_{site_id}_vectors"
        
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
        
        # 初始化Milvus向量存储
        self.vector_store = MilvusVectorStore(
            uri="",  # 设置为空字符串避免使用本地文件
            host=milvus_parsed.hostname,
            port=milvus_parsed.port,
            db_name=milvus_parsed.path[1:],
            collection_name=self.milvus_collection,
            dim=int(os.getenv("EMB_DIMENSIONS", 1536)),
            similarity_metric="cosine",
            enable_sparse=True,
            sparse_embedding_function=BGEM3SparseEmbeddingFunction(),
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
        
        # 初始化摄入管道
        self.pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(
                    chunk_size=512,
                    chunk_overlap=128,
                ),
                Settings.embed_model,
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
                text=doc_data['content'],
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

    async def remove_documents(self, doc_ids: List[str]) -> None:
        """
        从索引中删除文档
        
        Args:
            doc_ids: 要删除的文档ID列表
        """
        for doc_id in doc_ids:
            await self.index.adelete_ref_doc(
                ref_doc_id=doc_id,
                delete_from_docstore=True
            )
            await self.doc_store.adelete_document(doc_id)

    async def remove_all_documents(self) -> None:
        """删除该站点的所有文档"""
        all_docs = self.doc_store.docs
        for doc_id in all_docs.keys():
            if doc_id.startswith(f"{self.site_id}:"):
                await self.remove_documents([doc_id])

    async def get_document(self, doc_id: str) -> Optional[Document]:
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

    async def update_document(self, doc_id: str, new_content: str) -> bool:
        """
        更新文档内容
        
        Args:
            doc_id: 文档ID
            new_content: 新的文档内容
            
        Returns:
            bool: 更新是否成功
        """
        try:
            old_doc = await self.get_document(doc_id)
            if not old_doc:
                return False
                
            # 创建新文档，保留原有元数据
            new_doc = Document(
                text=new_content,
                id_=doc_id,
                metadata={
                    **old_doc.metadata,
                    "updated_at": datetime.now().isoformat()
                }
            )
            
            # 删除旧文档并添加新文档
            await self.remove_documents([doc_id])
            await self.pipeline.arun(documents=[new_doc])
            return True
        except Exception:
            return False

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rerank: bool = True,
        similarity_cutoff: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的最大文档数量
            rerank: 是否进行重排序
            similarity_cutoff: 相似度阈值
            
        Returns:
            List[Dict[str, Any]]: 检索结果列表
        """
        from llama_index.core import QueryBundle
        from llama_index.core.indices.vector_store import VectorIndexRetriever
        from llama_index.core.postprocessor import SimilarityPostprocessor
        
        # 创建检索器
        vector_retriever = VectorIndexRetriever(
            index=self.index,
            similarity_top_k=top_k * 10 if rerank else top_k,
        )
        
        # 执行检索
        qb = QueryBundle(query)
        nodes = await vector_retriever.aretrieve(qb)
        
        # 重排序处理
        if rerank:
            nodes = Settings.reranker.postprocess_nodes(nodes, qb)
            nodes = SimilarityPostprocessor(
                similarity_cutoff=similarity_cutoff
            ).postprocess_nodes(nodes)
            nodes = nodes[:top_k]
        
        # 格式化结果
        results = []
        for node in nodes:
            doc = await self.get_document(node.node.ref_doc_id)
            if doc:
                results.append({
                    "id": node.node.ref_doc_id,
                    "text": node.node.text,
                    "score": node.score if hasattr(node, 'score') else None,
                    "metadata": doc.metadata
                })
        
        return results

    async def query_with_context(
        self,
        query: str,
        top_k: int = 5,
        similarity_cutoff: float = 0.6,
        context_window: int = 3
    ) -> Dict[str, Any]:
        """
        带上下文的查询
        
        Args:
            query: 查询文本
            top_k: 返回的最大文档数量
            similarity_cutoff: 相似度阈值
            context_window: 上下文窗口大小
            
        Returns:
            Dict[str, Any]: 查询结果
        """
        from llama_index.core import QueryBundle, PromptTemplate
        
        # 自定义提示模板
        custom_prompt_str = (
            "基于以下上下文信息回答问题。确保回答基于提供的上下文，并提供相关的有效链接。\n"
            "---------------------\n"
            "{context_str}\n"
            "---------------------\n"
            "根据上下文信息，回答以下问题: {query_str}\n"
        )
        custom_prompt = PromptTemplate(custom_prompt_str)
        
        # 检索相关文档
        nodes = await self.retrieve(
            query=query,
            top_k=top_k,
            similarity_cutoff=similarity_cutoff
        )
        
        if not nodes:
            return {
                "response": "抱歉，没有找到相关信息。",
                "sources": []
            }
        
        # 构建查询引擎
        query_engine = self.index.as_query_engine(
            similarity_top_k=top_k,
            text_qa_template=custom_prompt
        )
        
        # 执行查询
        response = await query_engine.aquery(QueryBundle(query))
        
        return {
            "response": response.response,
            "sources": nodes
        }

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
        milvus_uri: str = os.getenv("MILVUS_URI")
    ) -> DataIndexer:
        """
        获取数据索引管理器实例，如果不存在则创建新实例
        
        Args:
            site_id: 站点ID
            redis_uri: Redis连接URI
            milvus_uri: Milvus连接URI
            
        Returns:
            DataIndexer: 数据索引管理器实例
        """
        if site_id not in cls._instances:
            cls._instances[site_id] = DataIndexer(
                redis_uri=redis_uri,
                milvus_uri=milvus_uri,
                site_id=site_id
            )
        return cls._instances[site_id] 